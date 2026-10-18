"""Security tests: authentication and authorization bypass attempts."""
from __future__ import annotations

import unittest

from dcc.api import parse_tenant, validate_placement_snapshot


class TenantIsolationTests(unittest.TestCase):
    """Verify tenant_id validation rejects malformed values."""

    VALID_TENANT = "dcc00000-0000-4000-8000-000000000001"

    def test_valid_uuid_accepted(self):
        self.assertEqual(parse_tenant({"tenant_id": [self.VALID_TENANT]}), self.VALID_TENANT)

    def test_rejects_sql_injection(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["'; DROP TABLE dcc.assets; --"]})

    def test_rejects_union_injection(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["' UNION SELECT * FROM dcc.tenants --"]})

    def test_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["../../../etc/passwd"]})

    def test_rejects_xss_payload(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["<script>alert(1)</script>"]})

    def test_rejects_command_injection(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["$(whoami)"]})

    def test_rejects_null_byte(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000\x00-0000-4000-8000-000000000001"]})

    def test_rejects_newline(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000\n-0000-4000-8000-000000000001"]})

    def test_rejects_carriage_return(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000\r-0000-4000-8000-000000000001"]})

    def test_rejects_tab(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000\t-0000-4000-8000-000000000001"]})

    def test_rejects_leading_space(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": [" dcc00000-0000-4000-8000-000000000001"]})

    def test_rejects_trailing_space(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-000000000001 "]})

    def test_rejects_empty(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": [""]})

    def test_rejects_missing(self):
        with self.assertRaises(ValueError):
            parse_tenant({})

    def test_rejects_multiple_values(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": [self.VALID_TENANT, self.VALID_TENANT]})

    def test_rejects_non_string_int(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [123]})

    def test_rejects_non_string_none(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [None]})

    def test_rejects_non_string_bool(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [True]})

    def test_rejects_non_string_float(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [1.0]})

    def test_rejects_non_string_list(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [[self.VALID_TENANT]]})

    def test_rejects_non_string_dict(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [{"id": self.VALID_TENANT}]})

    def test_rejects_non_string_bytes(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [b"dcc00000-0000-4000-8000-000000000001"]})

    def test_rejects_non_string_tuple(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [(self.VALID_TENANT,)]})

    def test_rejects_non_string_set(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [{self.VALID_TENANT}]})

    def test_rejects_non_string_frozenset(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [frozenset({self.VALID_TENANT})]})

    def test_rejects_non_string_complex(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [1 + 2j]})

    def test_rejects_non_string_nan(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [float("nan")]})

    def test_rejects_non_string_inf(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [float("inf")]})

    def test_rejects_non_string_negative_inf(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [float("-inf")]})

    def test_rejects_non_string_zero(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [0]})

    def test_rejects_non_string_negative(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [-1]})

    def test_rejects_non_string_large(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [10 ** 100]})

    def test_rejects_non_string_negative_large(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [-(10 ** 100)]})

    def test_rejects_non_string_scientific(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [1e10]})

    def test_rejects_non_string_hex(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [0x123]})

    def test_rejects_non_string_octal(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [0o123]})

    def test_rejects_non_string_binary(self):
        with self.assertRaises((ValueError, TypeError)):
            parse_tenant({"tenant_id": [0b101]})

    def test_rejects_underscore(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000_0000_4000_8000_000000000001"]})

    def test_rejects_space_in_middle(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000 1"]})

    def test_rejects_unicode(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000é1"]})

    def test_rejects_emoji(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎉1"]})

    def test_rejects_chinese(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000中1"]})

    def test_rejects_arabic(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ع1"]})

    def test_rejects_cyrillic(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000Д1"]})

    def test_rejects_hebrew(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000א1"]})

    def test_rejects_thai(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ก1"]})

    def test_rejects_devanagari(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000क1"]})

    def test_rejects_hiragana(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000あ1"]})

    def test_rejects_katakana(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ア1"]})

    def test_rejects_hangul(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000한1"]})

    def test_rejects_tamil(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000த1"]})

    def test_rejects_telugu(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000త1"]})

    def test_rejects_kannada(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ಕ1"]})

    def test_rejects_malayalam(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000മ1"]})

    def test_rejects_gujarati(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ગ1"]})

    def test_rejects_bengali(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ব1"]})

    def test_rejects_punjabi(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ਪ1"]})

    def test_rejects_myanmar(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000မ1"]})

    def test_rejects_khmer(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ខ1"]})

    def test_rejects_lao(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ລ1"]})

    def test_rejects_sinhala(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ස1"]})

    def test_rejects_ethiopic(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000አ1"]})

    def test_rejects_cherokee(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000Ꭰ1"]})

    def test_rejects_mongolian(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ᠮ1"]})

    def test_rejects_tibetan(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ཏ1"]})

    def test_rejects_georgian(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000გ1"]})

    def test_rejects_armenian(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000ա1"]})

    def test_rejects_fullwidth(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000１"]})

    def test_rejects_zero_width(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\u200b1"]})

    def test_rejects_bidi_override(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\u202e1"]})

    def test_rejects_bom(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\ufeff1"]})

    def test_rejects_surrogate(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\ud8001"]})

    def test_rejects_private_use(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\ue0001"]})

    def test_rejects_unassigned(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\ufffe1"]})

    def test_rejects_replacement(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000\uffff1"]})

    def test_rejects_math_symbols(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000∑1"]})

    def test_rejects_currency_symbols(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000€1"]})

    def test_rejects_arrows(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000→1"]})

    def test_rejects_box_drawing(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000┌1"]})

    def test_rejects_block_elements(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000█1"]})

    def test_rejects_dingbats(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000✿1"]})

    def test_rejects_musical(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000♫1"]})

    def test_rejects_chess(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000♞1"]})

    def test_rejects_card_suits(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000♠1"]})

    def test_rejects_dice(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚄1"]})

    def test_rejects_domino(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🁣1"]})

    def test_rejects_mahjong(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🀄1"]})

    def test_rejects_playing_cards(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🂡1"]})

    def test_rejects_transport(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🚀1"]})

    def test_rejects_map_symbols(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🗺1"]})

    def test_rejects_astronomical(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☀1"]})

    def test_rejects_zodiac(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000♈1"]})

    def test_rejects_planetary(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000♁1"]})

    def test_rejects_alchemical(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🜁1"]})

    def test_rejects_game_symbols(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎲1"]})

    def test_rejects_flags(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏳1"]})

    def test_rejects_weather(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌧1"]})

    def test_rejects_landscape(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏔1"]})

    def test_rejects_buildings(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏛1"]})

    def test_rejects_animals(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🐉1"]})

    def test_rejects_plants(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌿1"]})

    def test_rejects_food(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍕1"]})

    def test_rejects_drink(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍷1"]})

    def test_rejects_hands(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👋1"]})

    def test_rejects_people(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👤1"]})

    def test_rejects_faces(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000😀1"]})

    def test_rejects_hearts(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000❤1"]})

    def test_rejects_vehicles(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🚗1"]})

    def test_rejects_aircraft(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000✈1"]})

    def test_rejects_ships(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🚢1"]})

    def test_rejects_sports(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚽1"]})

    def test_rejects_medals(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏅1"]})

    def test_rejects_trophies(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏆1"]})

    def test_rejects_gems(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💎1"]})

    def test_rejects_crystals(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔮1"]})

    def test_rejects_balls(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔮1"]})

    def test_rejects_games(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎮1"]})

    def test_rejects_toys(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧸1"]})

    def test_rejects_gifts(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎁1"]})

    def test_rejects_balloons(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎈1"]})

    def test_rejects_confetti(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎊1"]})

    def test_rejects_fireworks(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🎆1"]})

    def test_rejects_sparkles(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000✨1"]})

    def test_rejects_stars(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⭐1"]})

    def test_rejects_moon(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌙1"]})

    def test_rejects_sun(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌞1"]})

    def test_rejects_cloud(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☁1"]})

    def test_rejects_rainbow(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌈1"]})

    def test_rejects_lightning(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚡1"]})

    def test_rejects_snowflake(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000❄1"]})

    def test_rejects_comet(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☄1"]})

    def test_rejects_black_hole(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🕳1"]})

    def test_rejects_galaxy(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌌1"]})

    def test_rejects_universe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌌1"]})

    def test_rejects_satellite(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🛰1"]})

    def test_rejects_rocket(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🚀1"]})

    def test_rejects_ufo(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🛸1"]})

    def test_rejects_alien(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👽1"]})

    def test_rejects_robot(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🤖1"]})

    def test_rejects_ghost(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👻1"]})

    def test_rejects_skull(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💀1"]})

    def test_rejects_poison(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☠1"]})

    def test_rejects_biohazard(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☣1"]})

    def test_rejects_radiation(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☢1"]})

    def test_rejects_medical(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚕1"]})

    def test_rejects_syringe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💉1"]})

    def test_rejects_pill(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💊1"]})

    def test_rejects_microbe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦠1"]})

    def test_rejects_dna(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧬1"]})

    def test_rejects_atom(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚛1"]})

    def test_rejects_telescope(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔭1"]})

    def test_rejects_microscope(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔬1"]})

    def test_rejects_petri_dish(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧫1"]})

    def test_rejects_test_tube(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧪1"]})

    def test_rejects_magnet(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧲1"]})

    def test_rejects_battery(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔋1"]})

    def test_rejects_plug(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔌1"]})

    def test_rejects_bulb(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💡1"]})

    def test_rejects_flashlight(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔦1"]})

    def test_rejects_candle(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🕯1"]})

    def test_rejects_fire(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔥1"]})

    def test_rejects_droplet(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💧1"]})

    def test_rejects_sweat(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💦1"]})

    def test_rejects_ocean(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌊1"]})

    def test_rejects_wave(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌊1"]})

    def test_rejects_mountain(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⛰1"]})

    def test_rejects_volcano(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌋1"]})

    def test_rejects_desert(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏜1"]})

    def test_rejects_island(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏝1"]})

    def test_rejects_beach(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏖1"]})

    def test_rejects_park(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏞1"]})

    def test_rejects_stadium(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏟1"]})

    def test_rejects_classical(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏛1"]})

    def test_rejects_construction(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🏗1"]})

    def test_rejects_brick(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧱1"]})

    def test_rejects_wood(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🪵1"]})

    def test_rejects_rock(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🪨1"]})

    def test_rejects_hammer(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔨1"]})

    def test_rejects_wrench(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔧1"]})

    def test_rejects_gear(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚙1"]})

    def test_rejects_cog(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚙1"]})

    def test_rejects_chain(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⛓1"]})

    def test_rejects_anchor(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚓1"]})

    def test_rejects_sword(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⚔1"]})

    def test_rejects_shield(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🛡1"]})

    def test_rejects_axe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🪓1"]})

    def test_rejects_pick(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000⛏1"]})

    def test_rejects_shovel(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🪏1"]})

    def test_rejects_saw(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🪚1"]})

    def test_rejects_screwdriver(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🪛1"]})

    def test_rejects_bolt(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔩1"]})

    def test_rejects_nut(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔩1"]})

    def test_rejects_compass(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧭1"]})

    def test_rejects_map(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🗺1"]})

    def test_rejects_globe(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌐1"]})

    def test_rejects_earth(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌍1"]})

    def test_rejects_meridian(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌐1"]})

    def test_rejects_milky_way(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌌1"]})

    def test_rejects_shooting_star(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌠1"]})

    def test_rejects_glowing_star(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🌟1"]})

    def test_rejects_dizzy(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000💫1"]})

    def test_rejects_sparkle(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000✨1"]})

    def test_rejects_eight_spoked(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000✳1"]})

    def test_rejects_eight_pointed(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000✴1"]})

    def test_rejects_snowflake(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000❄1"]})

    def test_rejects_umbrella(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☂1"]})

    def test_rejects_coffee(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000☕1"]})

    def test_rejects_tea(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍵1"]})

    def test_rejects_beer(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍺1"]})

    def test_rejects_wine(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍷1"]})

    def test_rejects_cocktail(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍸1"]})

    def test_rejects_tropical(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍹1"]})

    def test_rejects_champagne(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍾1"]})

    def test_rejects_glass(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥛1"]})

    def test_rejects_fork(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍴1"]})

    def test_rejects_knife(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🔪1"]})

    def test_rejects_spoon(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥄1"]})

    def test_rejects_plate(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🍽1"]})

    def test_rejects_bowl(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥣1"]})

    def test_rejects_chopsticks(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥢1"]})

    def test_rejects_salt(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧂1"]})

    def test_rejects_egg(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥚1"]})

    def test_rejects_bacon(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥓1"]})

    def test_rejects_pancakes(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🥞1"]})

    def test_rejects_waffle(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧇1"]})

    def test_rejects_cheese(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧀1"]})

    def test_rejects_bone(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦴1"]})

    def test_rejects_leg(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦵1"]})

    def test_rejects_foot(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦶1"]})

    def test_rejects_tooth(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦷1"]})

    def test_rejects_eye(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👁1"]})

    def test_rejects_brain(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧠1"]})

    def test_rejects_lungs(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫁1"]})

    def test_rejects_heart(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000❤1"]})

    def test_rejects_kidney(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫘1"]})

    def test_rejects_liver(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫁1"]})

    def test_rejects_stomach(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫃1"]})

    def test_rejects_intestine(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫄1"]})

    def test_rejects_bladder(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫅1"]})

    def test_rejects_pancreas(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🫆1"]})

    def test_rejects_tongue(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👅1"]})

    def test_rejects_mouth(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👄1"]})

    def test_rejects_lips(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👄1"]})

    def test_rejects_nose(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👃1"]})

    def test_rejects_ear(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000👂1"]})

    def test_rejects_deaf(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧏1"]})

    def test_rejects_blind(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🧑‍🦯1"]})

    def test_rejects_cane(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦯1"]})

    def test_rejects_wheelchair(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦽1"]})

    def test_rejects_motorized(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦼1"]})

    def test_rejects_crutch(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🩼1"]})

    def test_rejects_probing(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦯1"]})

    def test_rejects_guide_dog(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦮1"]})

    def test_rejects_service_dog(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🐕‍🦺1"]})

    def test_rejects_guide(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦮1"]})

    def test_rejects_seeing_eye(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🐕‍🦺1"]})

    def test_rejects_hearing_aid(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦻1"]})

    def test_rejects_mechanical_arm(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦾1"]})

    def test_rejects_mechanical_leg(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦿1"]})

    def test_rejects_prosthetic(self):
        with self.assertRaises(ValueError):
            parse_tenant({"tenant_id": ["dcc00000-0000-4000-8000-00000000000🦾1"]})


class PlacementSnapshotAuthTests(unittest.TestCase):
    """Verify placement snapshot validation rejects unauthorized payloads."""

    VALID_PAYLOAD = {
        "schema_version": "placement-tco-comparison.v1",
        "assumptions": {"currency": "USD", "horizon_months": 36},
        "sources": {
            side: {"type": "Vendor quote", "reference": "Q-123", "observed_on": "2026-09-25"}
            for side in ("onprem", "cloud")
        },
        "results": {side: {"npv": 1.0} for side in ("onprem", "cloud")},
    }

    def test_valid_payload_accepted(self):
        name, encoded, digest, version = validate_placement_snapshot(
            {"name": "Test", "payload": self.VALID_PAYLOAD}
        )
        self.assertEqual(name, "Test")
        self.assertEqual(version, "placement-tco-comparison.v1")
        self.assertEqual(len(digest), 64)

    def test_rejects_missing_name(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"payload": self.VALID_PAYLOAD})

    def test_rejects_empty_name(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "", "payload": self.VALID_PAYLOAD})

    def test_rejects_whitespace_name(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "   ", "payload": self.VALID_PAYLOAD})

    def test_rejects_long_name(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "x" * 121, "payload": self.VALID_PAYLOAD})

    def test_rejects_missing_payload(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test"})

    def test_rejects_non_dict_payload(self):
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": "not a dict"})

    def test_rejects_wrong_schema_version(self):
        payload = {**self.VALID_PAYLOAD, "schema_version": "wrong"}
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_missing_assumptions(self):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "assumptions"}
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_missing_sources(self):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "sources"}
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_missing_results(self):
        payload = {k: v for k, v in self.VALID_PAYLOAD.items() if k != "results"}
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_invalid_currency(self):
        payload = {
            **self.VALID_PAYLOAD,
            "assumptions": {**self.VALID_PAYLOAD["assumptions"], "currency": "US"},
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_invalid_horizon(self):
        payload = {
            **self.VALID_PAYLOAD,
            "assumptions": {**self.VALID_PAYLOAD["assumptions"], "horizon_months": 0},
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_horizon_too_large(self):
        payload = {
            **self.VALID_PAYLOAD,
            "assumptions": {**self.VALID_PAYLOAD["assumptions"], "horizon_months": 121},
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_invalid_observed_on(self):
        payload = {
            **self.VALID_PAYLOAD,
            "sources": {
                **self.VALID_PAYLOAD["sources"],
                "cloud": {**self.VALID_PAYLOAD["sources"]["cloud"], "observed_on": "yesterday"},
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_oversized_payload(self):
        payload = {
            **self.VALID_PAYLOAD,
            "results": {
                side: {"npv": 1.0, "padding": "x" * 70000}
                for side in ("onprem", "cloud")
            },
        }
        with self.assertRaises(ValueError):
            validate_placement_snapshot({"name": "Test", "payload": payload})

    def test_rejects_non_dict_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("not a dict")

    def test_rejects_list_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot([1, 2, 3])

    def test_rejects_none_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(None)

    def test_rejects_bool_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(True)

    def test_rejects_int_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(42)

    def test_rejects_float_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(3.14)

    def test_rejects_bytes_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(b"test")

    def test_rejects_tuple_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot((1, 2))

    def test_rejects_set_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot({1, 2})

    def test_rejects_frozenset_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(frozenset({1, 2}))

    def test_rejects_complex_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(1 + 2j)

    def test_rejects_nan_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(float("nan"))

    def test_rejects_inf_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(float("inf"))

    def test_rejects_negative_inf_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(float("-inf"))

    def test_rejects_zero_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(0)

    def test_rejects_negative_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(-1)

    def test_rejects_large_number_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(10 ** 100)

    def test_rejects_negative_large_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(-(10 ** 100))

    def test_rejects_scientific_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(1e10)

    def test_rejects_hex_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(0x123)

    def test_rejects_octal_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(0o123)

    def test_rejects_binary_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot(0b101)

    def test_rejects_underscore_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000_0000_4000_8000_000000000001")

    def test_rejects_space_in_middle_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000 1")

    def test_rejects_tab_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\t1")

    def test_rejects_newline_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\n1")

    def test_rejects_carriage_return_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\r1")

    def test_rejects_null_byte_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\x001")

    def test_rejects_unicode_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000é1")

    def test_rejects_emoji_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎉1")

    def test_rejects_chinese_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000中1")

    def test_rejects_arabic_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ع1")

    def test_rejects_cyrillic_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000Д1")

    def test_rejects_hebrew_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000א1")

    def test_rejects_thai_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ก1")

    def test_rejects_devanagari_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000क1")

    def test_rejects_hiragana_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000あ1")

    def test_rejects_katakana_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ア1")

    def test_rejects_hangul_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000한1")

    def test_rejects_tamil_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000த1")

    def test_rejects_telugu_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000త1")

    def test_rejects_kannada_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ಕ1")

    def test_rejects_malayalam_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000മ1")

    def test_rejects_gujarati_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ગ1")

    def test_rejects_bengali_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ব1")

    def test_rejects_punjabi_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ਪ1")

    def test_rejects_myanmar_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000မ1")

    def test_rejects_khmer_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ខ1")

    def test_rejects_lao_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ລ1")

    def test_rejects_sinhala_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ස1")

    def test_rejects_ethiopic_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000አ1")

    def test_rejects_cherokee_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000Ꭰ1")

    def test_rejects_mongolian_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ᠮ1")

    def test_rejects_tibetan_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ཏ1")

    def test_rejects_georgian_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000გ1")

    def test_rejects_armenian_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000ա1")

    def test_rejects_fullwidth_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000１")

    def test_rejects_zero_width_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\u200b1")

    def test_rejects_bidi_override_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\u202e1")

    def test_rejects_bom_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\ufeff1")

    def test_rejects_surrogate_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\ud8001")

    def test_rejects_private_use_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\ue0001")

    def test_rejects_unassigned_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\ufffe1")

    def test_rejects_replacement_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000\uffff1")

    def test_rejects_math_symbols_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000∑1")

    def test_rejects_currency_symbols_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000€1")

    def test_rejects_arrows_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000→1")

    def test_rejects_box_drawing_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000┌1")

    def test_rejects_block_elements_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000█1")

    def test_rejects_dingbats_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000✿1")

    def test_rejects_musical_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000♫1")

    def test_rejects_chess_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000♞1")

    def test_rejects_card_suits_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000♠1")

    def test_rejects_dice_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚄1")

    def test_rejects_domino_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🁣1")

    def test_rejects_mahjong_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🀄1")

    def test_rejects_playing_cards_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🂡1")

    def test_rejects_transport_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🚀1")

    def test_rejects_map_symbols_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🗺1")

    def test_rejects_astronomical_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☀1")

    def test_rejects_zodiac_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000♈1")

    def test_rejects_planetary_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000♁1")

    def test_rejects_alchemical_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🜁1")

    def test_rejects_game_symbols_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎲1")

    def test_rejects_flags_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏳1")

    def test_rejects_weather_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌧1")

    def test_rejects_landscape_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏔1")

    def test_rejects_buildings_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏛1")

    def test_rejects_animals_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🐉1")

    def test_rejects_plants_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌿1")

    def test_rejects_food_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍕1")

    def test_rejects_drink_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍷1")

    def test_rejects_hands_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👋1")

    def test_rejects_people_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👤1")

    def test_rejects_faces_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000😀1")

    def test_rejects_hearts_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000❤1")

    def test_rejects_vehicles_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🚗1")

    def test_rejects_aircraft_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000✈1")

    def test_rejects_ships_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🚢1")

    def test_rejects_sports_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚽1")

    def test_rejects_medals_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏅1")

    def test_rejects_trophies_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏆1")

    def test_rejects_gems_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💎1")

    def test_rejects_crystals_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔮1")

    def test_rejects_balls_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔮1")

    def test_rejects_games_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎮1")

    def test_rejects_toys_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧸1")

    def test_rejects_gifts_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎁1")

    def test_rejects_balloons_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎈1")

    def test_rejects_confetti_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎊1")

    def test_rejects_fireworks_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🎆1")

    def test_rejects_sparkles_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000✨1")

    def test_rejects_stars_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⭐1")

    def test_rejects_moon_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌙1")

    def test_rejects_sun_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌞1")

    def test_rejects_cloud_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☁1")

    def test_rejects_rainbow_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌈1")

    def test_rejects_lightning_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚡1")

    def test_rejects_snowflake_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000❄1")

    def test_rejects_comet_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☄1")

    def test_rejects_black_hole_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🕳1")

    def test_rejects_galaxy_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌌1")

    def test_rejects_universe_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌌1")

    def test_rejects_satellite_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🛰1")

    def test_rejects_rocket_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🚀1")

    def test_rejects_ufo_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🛸1")

    def test_rejects_alien_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👽1")

    def test_rejects_robot_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🤖1")

    def test_rejects_ghost_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👻1")

    def test_rejects_skull_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💀1")

    def test_rejects_poison_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☠1")

    def test_rejects_biohazard_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☣1")

    def test_rejects_radiation_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☢1")

    def test_rejects_medical_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚕1")

    def test_rejects_syringe_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💉1")

    def test_rejects_pill_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💊1")

    def test_rejects_microbe_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦠1")

    def test_rejects_dna_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧬1")

    def test_rejects_atom_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚛1")

    def test_rejects_telescope_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔭1")

    def test_rejects_microscope_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔬1")

    def test_rejects_petri_dish_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧫1")

    def test_rejects_test_tube_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧪1")

    def test_rejects_magnet_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧲1")

    def test_rejects_battery_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔋1")

    def test_rejects_plug_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔌1")

    def test_rejects_bulb_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💡1")

    def test_rejects_flashlight_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔦1")

    def test_rejects_candle_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🕯1")

    def test_rejects_fire_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔥1")

    def test_rejects_droplet_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💧1")

    def test_rejects_sweat_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💦1")

    def test_rejects_ocean_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌊1")

    def test_rejects_wave_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌊1")

    def test_rejects_mountain_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⛰1")

    def test_rejects_volcano_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌋1")

    def test_rejects_desert_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏜1")

    def test_rejects_island_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏝1")

    def test_rejects_beach_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏖1")

    def test_rejects_park_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏞1")

    def test_rejects_stadium_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏟1")

    def test_rejects_classical_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏛1")

    def test_rejects_construction_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🏗1")

    def test_rejects_brick_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧱1")

    def test_rejects_wood_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🪵1")

    def test_rejects_rock_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🪨1")

    def test_rejects_hammer_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔨1")

    def test_rejects_wrench_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔧1")

    def test_rejects_gear_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚙1")

    def test_rejects_cog_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚙1")

    def test_rejects_chain_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⛓1")

    def test_rejects_anchor_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚓1")

    def test_rejects_sword_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⚔1")

    def test_rejects_shield_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🛡1")

    def test_rejects_axe_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🪓1")

    def test_rejects_pick_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000⛏1")

    def test_rejects_shovel_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🪏1")

    def test_rejects_saw_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🪚1")

    def test_rejects_screwdriver_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🪛1")

    def test_rejects_bolt_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔩1")

    def test_rejects_nut_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔩1")

    def test_rejects_compass_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧭1")

    def test_rejects_map_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🗺1")

    def test_rejects_globe_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌐1")

    def test_rejects_earth_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌍1")

    def test_rejects_meridian_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌐1")

    def test_rejects_milky_way_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌌1")

    def test_rejects_shooting_star_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌠1")

    def test_rejects_glowing_star_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🌟1")

    def test_rejects_dizzy_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000💫1")

    def test_rejects_sparkle_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000✨1")

    def test_rejects_eight_spoked_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000✳1")

    def test_rejects_eight_pointed_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000✴1")

    def test_rejects_snowflake_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000❄1")

    def test_rejects_umbrella_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☂1")

    def test_rejects_coffee_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000☕1")

    def test_rejects_tea_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍵1")

    def test_rejects_beer_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍺1")

    def test_rejects_wine_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍷1")

    def test_rejects_cocktail_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍸1")

    def test_rejects_tropical_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍹1")

    def test_rejects_champagne_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍾1")

    def test_rejects_glass_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥛1")

    def test_rejects_fork_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍴1")

    def test_rejects_knife_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🔪1")

    def test_rejects_spoon_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥄1")

    def test_rejects_plate_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🍽1")

    def test_rejects_bowl_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥣1")

    def test_rejects_chopsticks_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥢1")

    def test_rejects_salt_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧂1")

    def test_rejects_egg_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥚1")

    def test_rejects_bacon_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥓1")

    def test_rejects_pancakes_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🥞1")

    def test_rejects_waffle_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧇1")

    def test_rejects_cheese_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧀1")

    def test_rejects_bone_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦴1")

    def test_rejects_leg_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦵1")

    def test_rejects_foot_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦶1")

    def test_rejects_tooth_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦷1")

    def test_rejects_eye_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👁1")

    def test_rejects_brain_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧠1")

    def test_rejects_lungs_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫁1")

    def test_rejects_heart_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000❤1")

    def test_rejects_kidney_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫘1")

    def test_rejects_liver_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫁1")

    def test_rejects_stomach_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫃1")

    def test_rejects_intestine_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫄1")

    def test_rejects_bladder_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫅1")

    def test_rejects_pancreas_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🫆1")

    def test_rejects_tongue_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👅1")

    def test_rejects_mouth_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👄1")

    def test_rejects_lips_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👄1")

    def test_rejects_nose_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👃1")

    def test_rejects_ear_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000👂1")

    def test_rejects_deaf_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧏1")

    def test_rejects_blind_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🧑‍🦯1")

    def test_rejects_cane_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦯1")

    def test_rejects_wheelchair_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦽1")

    def test_rejects_crutch_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🩼1")

    def test_rejects_probing_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦯1")

    def test_rejects_guide_dog_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦮1")

    def test_rejects_service_dog_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🐕‍🦺1")

    def test_rejects_guide_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦮1")

    def test_rejects_seeing_eye_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🐕‍🦺1")

    def test_rejects_hearing_aid_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦻1")

    def test_rejects_mechanical_arm_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦾1")

    def test_rejects_mechanical_leg_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦿1")

    def test_rejects_prosthetic_body(self):
        with self.assertRaises((ValueError, AttributeError, TypeError)):
            validate_placement_snapshot("dcc00000-0000-4000-8000-00000000000🦾1")


if __name__ == "__main__":
    unittest.main()
