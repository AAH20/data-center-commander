/**
 * Artillery processor functions for Data Center Commander performance tests.
 * Provides custom metrics, response validation, and scenario hooks.
 */

module.exports = {
  /**
   * Before request hook - can modify request or set variables
   */
  beforeRequest: (requestParams, context, ee, next) => {
    // Add timestamp for request tracking
    context.vars.requestStartTime = Date.now();
    return next();
  },

  /**
   * After response hook - capture custom metrics
   */
  afterResponse: (requestParams, response, context, ee, next) => {
    const duration = Date.now() - context.vars.requestStartTime;

    // Track response times by endpoint
    const url = requestParams.url || '';
    let endpoint = 'unknown';
    if (url.includes('/v2/overview')) endpoint = 'overview';
    else if (url.includes('/v2/assets')) endpoint = 'assets';
    else if (url.includes('/v2/facilities')) endpoint = 'facilities';
    else if (url.includes('/v2/workflows')) endpoint = 'workflows';
    else if (url.includes('/v2/analytics')) endpoint = 'analytics';
    else if (url.includes('/v2/topology')) endpoint = 'topology';
    else if (url.includes('/v2/costs')) endpoint = 'costs';
    else if (url.includes('/v2/capacity')) endpoint = 'capacity';
    else if (url.includes('/v2/evidence')) endpoint = 'evidence';
    else if (url.includes('/v2/connectors')) endpoint = 'connectors';
    else if (url.includes('/healthz')) endpoint = 'healthz';
    else if (url.includes('/readyz')) endpoint = 'readyz';

    // Emit custom metric
    ee.emit('histogram', `dcc.${endpoint}.response_time`, duration);

    // Track status codes
    const status = response.statusCode;
    ee.emit('counter', `dcc.${endpoint}.status_${status}`, 1);

    // Track errors
    if (status >= 500) {
      ee.emit('counter', `dcc.${endpoint}.server_errors`, 1);
    } else if (status >= 400) {
      ee.emit('counter', `dcc.${endpoint}.client_errors`, 1);
    }

    return next();
  },

  /**
   * Before scenario hook
   */
  beforeScenario: (context, ee, next) => {
    context.vars.scenarioStartTime = Date.now();
    return next();
  },

  /**
   * After scenario hook
   */
  afterScenario: (context, ee, next) => {
    const duration = Date.now() - context.vars.scenarioStartTime;
    ee.emit('histogram', 'dcc.scenario.duration', duration);
    return next();
  },
};
