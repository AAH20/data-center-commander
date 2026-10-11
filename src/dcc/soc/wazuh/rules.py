"""Wazuh OSS Detection Rules.

Wazuh rules in ossec.conf XML format covering:
- Brute force attacks (SSH, FTP, RDP)
- Web attacks (SQLi, XSS, webshells)
- Privilege escalation
- Malware and rootkit detection
- File integrity monitoring
- Cloud security (AWS, Azure, GCP)
- Container/Docker security
- Data exfiltration
- Lateral movement
- C2 beaconing
- Windows security events
"""

from typing import Any

# ---------------------------------------------------------------------------
# Wazuh XML Rules (ossec.conf format)
# ---------------------------------------------------------------------------

WAZUH_RULES_XML = """
<!-- ============================================================
     Wazuh OSS Detection Rules - Data Center Commander
     Version: 1.0.0
     ============================================================ -->

<group name="dcc,">

  <!-- ==================== SSH BRUTE FORCE ==================== -->
  <rule id="100001" level="10">
    <if_sid>5716</if_sid>
    <same_source_ip />
    <description>SSH brute force: multiple failed logins from same IP</description>
    <group>authentication_failures,pci_dss_10.2.4,pci_dss_10.2.5,gpg13_7.1,gdpr_IV_35.7.d,</group>
    <mitre>
      <id>T1110</id>
    </mitre>
  </rule>

  <rule id="100002" level="12">
    <if_sid>100001</if_sid>
    <same_source_ip />
    <frequency>10</frequency>
    <timeframe>120</timeframe>
    <description>SSH brute force: 10+ failed attempts in 2 minutes</description>
    <group>authentication_failures,brute_force,pci_dss_10.2.4,pci_dss_10.2.5,gpg13_7.1,gdpr_IV_35.7.d,</group>
    <mitre>
      <id>T1110.001</id>
    </mitre>
  </rule>

  <!-- ==================== FTP BRUTE FORCE ==================== -->
  <rule id="100003" level="10">
    <if_sid>5716</if_sid>
    <same_source_ip />
    <description>FTP brute force: multiple failed logins from same IP</description>
    <group>authentication_failures,pci_dss_10.2.4,pci_dss_10.2.5,</group>
    <mitre>
      <id>T1110.001</id>
    </mitre>
  </rule>

  <!-- ==================== RDP BRUTE FORCE ==================== -->
  <rule id="100004" level="10">
    <if_sid>5716</if_sid>
    <same_source_ip />
    <description>RDP brute force: multiple failed logins from same IP</description>
    <group>authentication_failures,pci_dss_10.2.4,pci_dss_10.2.5,</group>
    <mitre>
      <id>T1110.001</id>
    </mitre>
  </rule>

  <!-- ==================== WEB ATTACKS ==================== -->
  <rule id="100010" level="10">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(union.*select|select.*from|insert.*into|update.*set|delete.*from|drop.*table|create.*table|alter.*table)</field>
    <description>SQL injection attempt detected in URL</description>
    <group>web,sqli,attack,pci_dss_6.5.1,pci_dss_11.4,gdpr_IV_35.7.d,</group>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>

  <rule id="100011" level="10">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(&lt;script|&lt;img.*onerror|javascript:|onload=|onclick=|onmouseover=)</field>
    <description>XSS attempt detected in URL</description>
    <group>web,xss,attack,pci_dss_6.5.1,pci_dss_11.4,gdpr_IV_35.7.d,</group>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>

  <rule id="100012" level="12">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(\\.\\./|\\.\\.\\\\|%2e%2e%2f|%2e%2e/|\\.%2e|%2e\\.)</field>
    <description>Path traversal attempt detected</description>
    <group>web,lfi,attack,pci_dss_6.5.1,pci_dss_11.4,</group>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>

  <rule id="100013" level="12">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(cmd\\.exe|powershell\\.exe|bash\\.sh|/bin/sh|/bin/bash|whoami|net\\s+user|net\\s+localgroup)</field>
    <description>Command injection attempt detected</description>
    <group>web,rce,attack,pci_dss_6.5.1,pci_dss_11.4,</group>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>

  <rule id="100014" level="12">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(eval\\(|assert\\(|system\\(|exec\\(|shell_exec\\(|passthru\\(|popen\\(|proc_open\\()</field>
    <description>PHP code injection attempt detected</description>
    <group>web,rce,attack,pci_dss_6.5.1,pci_dss_11.4,</group>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>

  <!-- ==================== WEB SHELL DETECTION ==================== -->
  <rule id="100020" level="12">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(c99\\.php|r57\\.php|b374k\\.php|wso\\.php|adminer\\.php|eval-stdin\\.php)</field>
    <description>Known web shell detected</description>
    <group>web,webshell,attack,pci_dss_11.4,</group>
    <mitre>
      <id>T1505.003</id>
    </mitre>
  </rule>

  <rule id="100021" level="12">
    <if_sid>31100</if_sid>
    <field name="url" type="pcre2">(?i)(base64_decode\\(|gzinflate\\(|str_rot13\\(|preg_replace.*/e)</field>
    <description>Obfuscated PHP code detected - possible web shell</description>
    <group>web,webshell,attack,pci_dss_11.4,</group>
    <mitre>
      <id>T1505.003</id>
    </mitre>
  </rule>

  <!-- ==================== PRIVILEGE ESCALATION ==================== -->
  <rule id="100030" level="10">
    <if_sid>5716</if_sid>
    <field name="user" type="pcre2">(?i)(root|admin|administrator|system)</field>
    <description>Privilege escalation: failed login as privileged user</description>
    <group>privilege_escalation,pci_dss_10.2.4,pci_dss_10.2.5,</group>
    <mitre>
      <id>T1068</id>
    </mitre>
  </rule>

  <rule id="100031" level="12">
    <if_sid>5716</if_sid>
    <field name="user" type="pcre2">(?i)(root|admin|administrator|system)</field>
    <same_source_ip />
    <frequency>5</frequency>
    <timeframe>60</timeframe>
    <description>Privilege escalation: 5+ failed logins as privileged user in 1 minute</description>
    <group>privilege_escalation,pci_dss_10.2.4,pci_dss_10.2.5,</group>
    <mitre>
      <id>T1068</id>
    </mitre>
  </rule>

  <!-- ==================== SUDO ABUSE ==================== -->
  <rule id="100032" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(sudo|su)</field>
    <description>Sudo/su authentication failure</description>
    <group>privilege_escalation,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1068</id>
    </mitre>
  </rule>

  <!-- ==================== MALWARE DETECTION ==================== -->
  <rule id="100040" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(clamav|freshclam)</field>
    <description>ClamAV malware detection</description>
    <group>malware,pci_dss_11.4,</group>
    <mitre>
      <id>T1059</id>
    </mitre>
  </rule>

  <rule id="100041" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(virus|trojan|malware|backdoor|rootkit|worm)</field>
    <description>Wazuh malware detection alert</description>
    <group>malware,pci_dss_11.4,</group>
    <mitre>
      <id>T1059</id>
    </mitre>
  </rule>

  <!-- ==================== ROOTKIT DETECTION ==================== -->
  <rule id="100050" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(rkhunter|chkrootkit)</field>
    <description>Rootkit detection alert</description>
    <group>rootkit,pci_dss_11.4,</group>
    <mitre>
      <id>T1014</id>
    </mitre>
  </rule>

  <!-- ==================== FILE INTEGRITY MONITORING ==================== -->
  <rule id="100060" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(integrity|checksum|md5|sha1|sha256)</field>
    <description>File integrity monitoring alert</description>
    <group>fim,pci_dss_11.5,</group>
    <mitre>
      <id>T1089</id>
    </mitre>
  </rule>

  <rule id="100061" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(added|deleted|modified)</field>
    <description>File integrity: file added/deleted/modified</description>
    <group>fim,pci_dss_11.5,</group>
    <mitre>
      <id>T1089</id>
    </mitre>
  </rule>

  <!-- ==================== CLOUD SECURITY - AWS ==================== -->
  <rule id="100070" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(aws|cloudtrail|guardduty)</field>
    <description>AWS CloudTrail security event</description>
    <group>cloud,aws,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <rule id="100071" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(aws|cloudtrail)</field>
    <field name="message" type="pcre2">(?i)(unauthorized|failed|error|denied)</field>
    <description>AWS unauthorized API call detected</description>
    <group>cloud,aws,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <!-- ==================== CLOUD SECURITY - AZURE ==================== -->
  <rule id="100072" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(azure|sentinel|defender)</field>
    <description>Azure security event</description>
    <group>cloud,azure,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <!-- ==================== CLOUD SECURITY - GCP ==================== -->
  <rule id="100073" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(gcp|google.*cloud|cloud.*command.*center)</field>
    <description>GCP security event</description>
    <group>cloud,gcp,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <!-- ==================== CONTAINER SECURITY ==================== -->
  <rule id="100080" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(docker|containerd|kubernetes|k8s)</field>
    <description>Container security event</description>
    <group>container,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1610</id>
    </mitre>
  </rule>

  <rule id="100081" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(docker|containerd|kubernetes|k8s)</field>
    <field name="message" type="pcre2">(?i)(privileged|host.*network|host.*pid|host.*ipc)</field>
    <description>Container running with elevated privileges</description>
    <group>container,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1610</id>
    </mitre>
  </rule>

  <!-- ==================== DATA EXFILTRATION ==================== -->
  <rule id="100090" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(large.*transfer|exfiltration|data.*leak)</field>
    <description>Potential data exfiltration detected</description>
    <group>exfiltration,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1041</id>
    </mitre>
  </rule>

  <!-- ==================== LATERAL MOVEMENT ==================== -->
  <rule id="100100" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(smb|rdp|winrm|ssh)</field>
    <description>Lateral movement: remote service connection</description>
    <group>lateral_movement,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1021</id>
    </mitre>
  </rule>

  <rule id="100101" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(smb|rdp|winrm|ssh)</field>
    <same_source_ip />
    <frequency>10</frequency>
    <timeframe>60</timeframe>
    <description>Lateral movement: 10+ remote connections in 1 minute</description>
    <group>lateral_movement,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1021</id>
    </mitre>
  </rule>

  <!-- ==================== C2 BEACONING ==================== -->
  <rule id="100110" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(beacon|heartbeat|c2|command.*and.*control)</field>
    <description>Potential C2 beaconing detected</description>
    <group>c2,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1071</id>
    </mitre>
  </rule>

  <!-- ==================== WINDOWS SECURITY EVENTS ==================== -->
  <rule id="100120" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(windows|security|system)</field>
    <field name="message" type="pcre2">(?i)(4625|4648|4672|4720|4726|4732|4738|4740|4756)</field>
    <description>Windows security event: account management</description>
    <group>windows,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <rule id="100121" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(windows|security)</field>
    <field name="message" type="pcre2">(?i)(4625)</field>
    <same_source_ip />
    <frequency>10</frequency>
    <timeframe>60</timeframe>
    <description>Windows: 10+ failed logins in 1 minute (Event ID 4625)</description>
    <group>windows,brute_force,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1110</id>
    </mitre>
  </rule>

  <rule id="100122" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(windows|security)</field>
    <field name="message" type="pcre2">(?i)(4672)</field>
    <description>Windows: special privileges assigned to new logon (Event ID 4672)</description>
    <group>windows,privilege_escalation,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1068</id>
    </mitre>
  </rule>

  <!-- ==================== ANOMALY DETECTION ==================== -->
  <rule id="100130" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(anomaly|outlier|unusual|abnormal)</field>
    <description>Anomaly detection alert</description>
    <group>anomaly,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <!-- ==================== POLICY VIOLATION ==================== -->
  <rule id="100140" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(policy|violation|compliance)</field>
    <description>Policy violation detected</description>
    <group>policy,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <!-- ==================== DDOS DETECTION ==================== -->
  <rule id="100150" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(ddos|denial.*service|flood|syn.*flood)</field>
    <description>Potential DDoS attack detected</description>
    <group>ddos,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1498</id>
    </mitre>
  </rule>

  <!-- ==================== CRYPTOJACKING ==================== -->
  <rule id="100160" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(mining|monero|bitcoin|cryptojack|xmrig|minerd)</field>
    <description>Potential cryptojacking activity detected</description>
    <group>cryptojacking,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1496</id>
    </mitre>
  </rule>

  <!-- ==================== INSIDER THREAT ==================== -->
  <rule id="100170" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(insider|data.*theft|unauthorized.*access)</field>
    <description>Potential insider threat detected</description>
    <group>insider_threat,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1078</id>
    </mitre>
  </rule>

  <!-- ==================== RANSOMWARE ==================== -->
  <rule id="100180" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(ransomware|encrypt.*file|locked.*file|decrypt.*file)</field>
    <description>Potential ransomware activity detected</description>
    <group>ransomware,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1486</id>
    </mitre>
  </rule>

  <!-- ==================== PHISHING ==================== -->
  <rule id="100190" level="10">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(phish|spear.*phish|credential.*harvest)</field>
    <description>Potential phishing activity detected</description>
    <group>phishing,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1566</id>
    </mitre>
  </rule>

  <!-- ==================== ZERO DAY ==================== -->
  <rule id="100200" level="12">
    <if_sid>5716</if_sid>
    <field name="program_name" type="pcre2">(?i)(ossec|wazuh)</field>
    <field name="message" type="pcre2">(?i)(zero.*day|0day|unknown.*exploit|novel.*attack)</field>
    <description>Potential zero-day exploit detected</description>
    <group>zero_day,pci_dss_10.2.4,</group>
    <mitre>
      <id>T1190</id>
    </mitre>
  </rule>

</group>
"""


# ---------------------------------------------------------------------------
# Structured Rule Definitions (for programmatic access)
# ---------------------------------------------------------------------------

WAZUH_RULES: list[dict[str, Any]] = [
    {
        "id": "WAZUH-001",
        "name": "SSH Brute Force",
        "description": "Detects SSH brute force attempts by counting failed authentication events from a single source IP.",
        "severity": "HIGH",
        "category": "brute_force",
        "mitre_technique": "T1110",
        "mitre_tactic": "Credential Access",
        "data_source": "syslog",
        "rule_ids": [100001, 100002],
        "frequency": 10,
        "timeframe": 120,
        "threshold": 10,
        "alert": {
            "title": "SSH Brute Force Detected",
            "description": "Multiple failed SSH login attempts from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-002",
        "name": "FTP Brute Force",
        "description": "Detects FTP brute force attempts.",
        "severity": "HIGH",
        "category": "brute_force",
        "mitre_technique": "T1110.001",
        "mitre_tactic": "Credential Access",
        "data_source": "syslog",
        "rule_ids": [100003],
        "alert": {
            "title": "FTP Brute Force Detected",
            "description": "Multiple failed FTP login attempts from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-003",
        "name": "RDP Brute Force",
        "description": "Detects RDP brute force attempts.",
        "severity": "HIGH",
        "category": "brute_force",
        "mitre_technique": "T1110.001",
        "mitre_tactic": "Credential Access",
        "data_source": "syslog",
        "rule_ids": [100004],
        "alert": {
            "title": "RDP Brute Force Detected",
            "description": "Multiple failed RDP login attempts from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-010",
        "name": "SQL Injection Attempt",
        "description": "Detects SQL injection patterns in web requests.",
        "severity": "HIGH",
        "category": "attack",
        "mitre_technique": "T1190",
        "mitre_tactic": "Initial Access",
        "data_source": "web",
        "rule_ids": [100010],
        "alert": {
            "title": "SQL Injection Attempt",
            "description": "SQL injection pattern detected from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-011",
        "name": "XSS Attempt",
        "description": "Detects cross-site scripting attempts in web requests.",
        "severity": "HIGH",
        "category": "attack",
        "mitre_technique": "T1190",
        "mitre_tactic": "Initial Access",
        "data_source": "web",
        "rule_ids": [100011],
        "alert": {
            "title": "XSS Attempt Detected",
            "description": "XSS pattern detected from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-012",
        "name": "Path Traversal Attempt",
        "description": "Detects path traversal / LFI attempts.",
        "severity": "HIGH",
        "category": "attack",
        "mitre_technique": "T1190",
        "mitre_tactic": "Initial Access",
        "data_source": "web",
        "rule_ids": [100012],
        "alert": {
            "title": "Path Traversal Attempt",
            "description": "Path traversal pattern detected from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-013",
        "name": "Command Injection Attempt",
        "description": "Detects command injection / RCE attempts.",
        "severity": "CRITICAL",
        "category": "attack",
        "mitre_technique": "T1190",
        "mitre_tactic": "Initial Access",
        "data_source": "web",
        "rule_ids": [100013],
        "alert": {
            "title": "Command Injection Attempt",
            "description": "Command injection pattern detected from {source_ip}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-014",
        "name": "PHP Code Injection",
        "description": "Detects PHP code injection attempts.",
        "severity": "CRITICAL",
        "category": "attack",
        "mitre_technique": "T1190",
        "mitre_tactic": "Initial Access",
        "data_source": "web",
        "rule_ids": [100014],
        "alert": {
            "title": "PHP Code Injection Attempt",
            "description": "PHP code injection pattern detected from {source_ip}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-020",
        "name": "Web Shell Detection",
        "description": "Detects known web shell files and activity.",
        "severity": "CRITICAL",
        "category": "persistence",
        "mitre_technique": "T1505.003",
        "mitre_tactic": "Persistence",
        "data_source": "web",
        "rule_ids": [100020, 100021],
        "alert": {
            "title": "Web Shell Detected",
            "description": "Known web shell detected: {url}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-030",
        "name": "Privilege Escalation",
        "description": "Detects privilege escalation attempts via sudo/su abuse.",
        "severity": "HIGH",
        "category": "privilege_escalation",
        "mitre_technique": "T1068",
        "mitre_tactic": "Privilege Escalation",
        "data_source": "syslog",
        "rule_ids": [100030, 100031, 100032],
        "alert": {
            "title": "Privilege Escalation Attempt",
            "description": "Multiple privilege escalation failures on {hostname}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-040",
        "name": "Malware Detection",
        "description": "Detects malware via ClamAV and Wazuh alerts.",
        "severity": "CRITICAL",
        "category": "malware",
        "mitre_technique": "T1059",
        "mitre_tactic": "Execution",
        "data_source": "syslog",
        "rule_ids": [100040, 100041],
        "alert": {
            "title": "Malware Detected",
            "description": "Malware detected: {message}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-050",
        "name": "Rootkit Detection",
        "description": "Detects rootkit activity via rkhunter/chkrootkit.",
        "severity": "CRITICAL",
        "category": "rootkit",
        "mitre_technique": "T1014",
        "mitre_tactic": "Defense Evasion",
        "data_source": "syslog",
        "rule_ids": [100050],
        "alert": {
            "title": "Rootkit Detected",
            "description": "Rootkit detected on {hostname}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-060",
        "name": "File Integrity Monitoring",
        "description": "Detects unauthorized file changes via FIM.",
        "severity": "MEDIUM",
        "category": "fim",
        "mitre_technique": "T1089",
        "mitre_tactic": "Defense Evasion",
        "data_source": "syslog",
        "rule_ids": [100060, 100061],
        "alert": {
            "title": "File Integrity Violation",
            "description": "File integrity violation detected on {hostname}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-070",
        "name": "AWS Security Event",
        "description": "Detects AWS CloudTrail security events.",
        "severity": "MEDIUM",
        "category": "cloud",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "cloud",
        "rule_ids": [100070, 100071],
        "alert": {
            "title": "AWS Security Event",
            "description": "AWS security event detected: {message}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-072",
        "name": "Azure Security Event",
        "description": "Detects Azure Sentinel/Defender security events.",
        "severity": "MEDIUM",
        "category": "cloud",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "cloud",
        "rule_ids": [100072],
        "alert": {
            "title": "Azure Security Event",
            "description": "Azure security event detected: {message}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-073",
        "name": "GCP Security Event",
        "description": "Detects GCP security events.",
        "severity": "MEDIUM",
        "category": "cloud",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "cloud",
        "rule_ids": [100073],
        "alert": {
            "title": "GCP Security Event",
            "description": "GCP security event detected: {message}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-080",
        "name": "Container Security Event",
        "description": "Detects container/Docker/Kubernetes security events.",
        "severity": "HIGH",
        "category": "container",
        "mitre_technique": "T1610",
        "mitre_tactic": "Defense Evasion",
        "data_source": "container",
        "rule_ids": [100080, 100081],
        "alert": {
            "title": "Container Security Event",
            "description": "Container security event detected: {message}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-090",
        "name": "Data Exfiltration",
        "description": "Detects potential data exfiltration.",
        "severity": "CRITICAL",
        "category": "exfiltration",
        "mitre_technique": "T1041",
        "mitre_tactic": "Exfiltration",
        "data_source": "syslog",
        "rule_ids": [100090],
        "alert": {
            "title": "Data Exfiltration Detected",
            "description": "Potential data exfiltration detected: {message}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-100",
        "name": "Lateral Movement",
        "description": "Detects lateral movement via SMB/RDP/WinRM/SSH.",
        "severity": "HIGH",
        "category": "lateral_movement",
        "mitre_technique": "T1021",
        "mitre_tactic": "Lateral Movement",
        "data_source": "syslog",
        "rule_ids": [100100, 100101],
        "alert": {
            "title": "Lateral Movement Detected",
            "description": "Lateral movement detected from {source_ip}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-110",
        "name": "C2 Beaconing",
        "description": "Detects C2 beaconing patterns.",
        "severity": "CRITICAL",
        "category": "command_and_control",
        "mitre_technique": "T1071",
        "mitre_tactic": "Command and Control",
        "data_source": "syslog",
        "rule_ids": [100110],
        "alert": {
            "title": "C2 Beaconing Detected",
            "description": "Potential C2 beaconing detected: {message}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-120",
        "name": "Windows Account Management",
        "description": "Detects Windows account management events.",
        "severity": "MEDIUM",
        "category": "windows",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "windows",
        "rule_ids": [100120, 100121, 100122],
        "alert": {
            "title": "Windows Security Event",
            "description": "Windows security event detected: {message}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-130",
        "name": "Anomaly Detection",
        "description": "Detects anomalous behavior patterns.",
        "severity": "MEDIUM",
        "category": "anomaly",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "syslog",
        "rule_ids": [100130],
        "alert": {
            "title": "Anomaly Detected",
            "description": "Anomalous behavior detected: {message}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-140",
        "name": "Policy Violation",
        "description": "Detects policy violations.",
        "severity": "MEDIUM",
        "category": "policy",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "syslog",
        "rule_ids": [100140],
        "alert": {
            "title": "Policy Violation",
            "description": "Policy violation detected: {message}",
            "priority": "P3",
        },
    },
    {
        "id": "WAZUH-150",
        "name": "DDoS Detection",
        "description": "Detects potential DDoS attacks.",
        "severity": "CRITICAL",
        "category": "ddos",
        "mitre_technique": "T1498",
        "mitre_tactic": "Impact",
        "data_source": "syslog",
        "rule_ids": [100150],
        "alert": {
            "title": "DDoS Attack Detected",
            "description": "Potential DDoS attack detected: {message}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-160",
        "name": "Cryptojacking",
        "description": "Detects cryptojacking activity.",
        "severity": "CRITICAL",
        "category": "cryptojacking",
        "mitre_technique": "T1496",
        "mitre_tactic": "Impact",
        "data_source": "syslog",
        "rule_ids": [100160],
        "alert": {
            "title": "Cryptojacking Detected",
            "description": "Potential cryptojacking activity detected: {message}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-170",
        "name": "Insider Threat",
        "description": "Detects potential insider threats.",
        "severity": "HIGH",
        "category": "insider_threat",
        "mitre_technique": "T1078",
        "mitre_tactic": "Initial Access",
        "data_source": "syslog",
        "rule_ids": [100170],
        "alert": {
            "title": "Insider Threat Detected",
            "description": "Potential insider threat detected: {message}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-180",
        "name": "Ransomware Detection",
        "description": "Detects potential ransomware activity.",
        "severity": "CRITICAL",
        "category": "ransomware",
        "mitre_technique": "T1486",
        "mitre_tactic": "Impact",
        "data_source": "syslog",
        "rule_ids": [100180],
        "alert": {
            "title": "Ransomware Detected",
            "description": "Potential ransomware activity detected: {message}",
            "priority": "P1",
        },
    },
    {
        "id": "WAZUH-190",
        "name": "Phishing Detection",
        "description": "Detects potential phishing activity.",
        "severity": "HIGH",
        "category": "phishing",
        "mitre_technique": "T1566",
        "mitre_tactic": "Initial Access",
        "data_source": "syslog",
        "rule_ids": [100190],
        "alert": {
            "title": "Phishing Detected",
            "description": "Potential phishing activity detected: {message}",
            "priority": "P2",
        },
    },
    {
        "id": "WAZUH-200",
        "name": "Zero-Day Exploit",
        "description": "Detects potential zero-day exploits.",
        "severity": "CRITICAL",
        "category": "zero_day",
        "mitre_technique": "T1190",
        "mitre_tactic": "Initial Access",
        "data_source": "syslog",
        "rule_ids": [100200],
        "alert": {
            "title": "Zero-Day Exploit Detected",
            "description": "Potential zero-day exploit detected: {message}",
            "priority": "P1",
        },
    },
]


def get_rules_xml() -> str:
    """Return the Wazuh XML rules for ossec.conf."""
    return WAZUH_RULES_XML.strip()


def get_rules() -> list[dict[str, Any]]:
    """Return structured rule definitions."""
    return WAZUH_RULES


def get_rule_by_id(rule_id: str) -> dict[str, Any] | None:
    """Get a single rule by its ID."""
    for rule in WAZUH_RULES:
        if rule["id"] == rule_id:
            return rule
    return None


def get_rules_by_category(category: str) -> list[dict[str, Any]]:
    """Get all rules in a given category."""
    return [r for r in WAZUH_RULES if r["category"] == category]


def get_rules_by_severity(severity: str) -> list[dict[str, Any]]:
    """Get all rules with a given severity."""
    return [r for r in WAZUH_RULES if r["severity"] == severity]


def get_rules_by_mitre(technique: str) -> list[dict[str, Any]]:
    """Get all rules for a given MITRE ATT&CK technique."""
    return [r for r in WAZUH_RULES if r["mitre_technique"] == technique]
