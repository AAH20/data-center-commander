"""Tests for unit conversion system with precision tracking."""

import unittest
from decimal import Decimal

from dcc.validation.units import (
    Dimension,
    Quantity,
    Unit,
    UnitRegistry,
    assert_same_dimension,
    compute_carbon_emissions,
    compute_cooling_load,
    compute_dcime,
    compute_energy_from_power,
    compute_power_from_energy,
    compute_pue,
    compute_ups_runtime,
    convert,
    convert_many,
    convert_temperature,
    convert_with_power_factor,
    c_to_f,
    f_to_c,
    format_quantity,
    get_registry,
    kw_to_kva,
    kw_to_mw,
    kva_to_kw,
    kwh_to_mwh,
    make_quantity,
    mwh_to_kwh,
    mw_to_kw,
    normalize_to_base,
    va_to_kva,
    va_to_w,
    validate_range,
    validate_same_dimension,
    w_to_va,
)


class TestDimension(unittest.TestCase):
    def test_dimension_enum_values(self):
        self.assertEqual(Dimension.POWER.value, "power")
        self.assertEqual(Dimension.ENERGY.value, "energy")
        self.assertEqual(Dimension.TEMPERATURE.value, "temperature")
        self.assertEqual(Dimension.PRESSURE.value, "pressure")
        self.assertEqual(Dimension.FLOW.value, "flow")


class TestUnit(unittest.TestCase):
    def test_unit_creation(self):
        u = Unit("watt", "W", Dimension.POWER, Decimal(1))
        self.assertEqual(u.name, "watt")
        self.assertEqual(u.symbol, "W")
        self.assertEqual(u.dimension, Dimension.POWER)
        self.assertEqual(u.to_base, Decimal(1))

    def test_unit_zero_to_base_raises(self):
        with self.assertRaises(ValueError):
            Unit("bad", "bad", Dimension.POWER, Decimal(0))

    def test_unit_with_offset(self):
        u = Unit("celsius", "°C", Dimension.TEMPERATURE, Decimal(1), Decimal(273.15))
        self.assertEqual(u.offset, Decimal(273.15))


class TestQuantity(unittest.TestCase):
    def test_quantity_creation(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w)
        self.assertEqual(q.value, Decimal("100"))
        self.assertEqual(q.unit, w)
        self.assertIsNone(q.sig_figs)

    def test_quantity_with_sig_figs(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w, sig_figs=3)
        self.assertEqual(q.sig_figs, 3)

    def test_quantity_invalid_sig_figs(self):
        reg = get_registry()
        w = reg.get("W")
        with self.assertRaises(ValueError):
            Quantity(Decimal("100"), w, sig_figs=0)

    def test_quantity_zero_normalization(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("-0"), w)
        self.assertEqual(q.value, Decimal(0))

    def test_quantity_repr(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w, sig_figs=3)
        r = repr(q)
        self.assertIn("100", r)
        self.assertIn("W", r)
        self.assertIn("sig_figs=3", r)

    def test_quantity_str(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w)
        self.assertEqual(str(q), "100 W")

    def test_quantity_equality(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("100"), w)
        q3 = Quantity(Decimal("200"), w)
        self.assertEqual(q1, q2)
        self.assertNotEqual(q1, q3)

    def test_quantity_add_same_unit(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("200"), w)
        result = q1 + q2
        self.assertEqual(result.value, Decimal("300"))
        self.assertEqual(result.unit, w)

    def test_quantity_add_different_units(self):
        reg = get_registry()
        kw = reg.get("kW")
        w = reg.get("W")
        q1 = Quantity(Decimal("1"), kw)
        q2 = Quantity(Decimal("500"), w)
        result = q1 + q2
        self.assertEqual(result.value, Decimal("1.5"))
        self.assertEqual(result.unit, kw)

    def test_quantity_add_different_dimensions_raises(self):
        reg = get_registry()
        w = reg.get("W")
        kwh = reg.get("kWh")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("200"), kwh)
        with self.assertRaises(ValueError):
            q1 + q2

    def test_quantity_sub(self):
        reg = get_registry()
        kw = reg.get("kW")
        w = reg.get("W")
        q1 = Quantity(Decimal("2"), kw)
        q2 = Quantity(Decimal("500"), w)
        result = q1 - q2
        self.assertEqual(result.value, Decimal("1.5"))
        self.assertEqual(result.unit, kw)

    def test_quantity_mul(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w, sig_figs=3)
        result = q * Decimal("2.0")
        self.assertEqual(result.value, Decimal("200.0"))
        self.assertEqual(result.sig_figs, 2)

    def test_quantity_mul_int(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w)
        result = q * 2
        self.assertEqual(result.value, Decimal("200"))

    def test_quantity_rmul(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w)
        result = 2 * q
        self.assertEqual(result.value, Decimal("200"))

    def test_quantity_div(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w, sig_figs=3)
        result = q / Decimal("2.0")
        self.assertEqual(result.value, Decimal("50.0"))
        self.assertEqual(result.sig_figs, 2)

    def test_quantity_div_zero_raises(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w)
        with self.assertRaises(ZeroDivisionError):
            q / Decimal(0)

    def test_quantity_to(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q = Quantity(Decimal("1500"), kw)
        result = q.to(mw)
        self.assertEqual(result.value, Decimal("1.5"))
        self.assertEqual(result.unit, mw)

    def test_quantity_to_base(self):
        reg = get_registry()
        kw = reg.get("kW")
        w = reg.get("W")
        q = Quantity(Decimal("1.5"), kw)
        result = q.to_base()
        self.assertEqual(result.value, Decimal("1500"))
        self.assertEqual(result.unit, w)


class TestUnitRegistry(unittest.TestCase):
    def test_get_by_symbol(self):
        reg = get_registry()
        w = reg.get("W")
        self.assertEqual(w.symbol, "W")
        self.assertEqual(w.dimension, Dimension.POWER)

    def test_get_by_name(self):
        reg = get_registry()
        w = reg.get("watt")
        self.assertEqual(w.symbol, "W")

    def test_get_unknown_raises(self):
        reg = get_registry()
        with self.assertRaises(KeyError):
            reg.get("unknown_unit")

    def test_get_base_unit(self):
        reg = get_registry()
        base = reg.get_base_unit(Dimension.POWER)
        self.assertEqual(base.symbol, "W")

    def test_get_base_unit_unknown_dimension(self):
        reg = get_registry()
        # All enum dimensions have base units; verify CURRENCY returns USD
        base = reg.get_base_unit(Dimension.CURRENCY)
        self.assertEqual(base.symbol, "USD")

    def test_list_units_by_dimension(self):
        reg = get_registry()
        power_units = reg.list_units(Dimension.POWER)
        symbols = [u.symbol for u in power_units]
        self.assertIn("W", symbols)
        self.assertIn("kW", symbols)
        self.assertIn("MW", symbols)
        self.assertIn("VA", symbols)

    def test_list_all_units(self):
        reg = get_registry()
        all_units = reg.list_units()
        self.assertGreater(len(all_units), 50)

    def test_register_custom_unit(self):
        reg = UnitRegistry()
        custom = Unit("custom watt", "cW", Dimension.POWER, Decimal("0.5"))
        reg.register(custom)
        retrieved = reg.get("cW")
        self.assertEqual(retrieved.name, "custom watt")

    def test_register_with_aliases(self):
        reg = UnitRegistry()
        custom = Unit("kilowatt", "kW", Dimension.POWER, Decimal(1000))
        reg.register(custom, aliases=["kilowatt", "Kilowatt"])
        self.assertEqual(reg.get("kilowatt").symbol, "kW")


class TestConvert(unittest.TestCase):
    def test_convert_w_to_kw(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        q = Quantity(Decimal("1500"), w)
        result = convert(q, kw)
        self.assertEqual(result.value, Decimal("1.5"))
        self.assertEqual(result.unit, kw)

    def test_convert_kw_to_mw(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q = Quantity(Decimal("1500"), kw)
        result = convert(q, mw)
        self.assertEqual(result.value, Decimal("1.5"))

    def test_convert_kwh_to_mwh(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        mwh = reg.get("MWh")
        q = Quantity(Decimal("100"), kwh)
        result = convert(q, mwh)
        self.assertEqual(result.value, Decimal("0.1"))

    def test_convert_with_string_target(self):
        reg = get_registry()
        kw = reg.get("kW")
        q = Quantity(Decimal("1500"), kw)
        result = convert(q, "MW")
        self.assertEqual(result.value, Decimal("1.5"))

    def test_convert_with_source_unit(self):
        result = convert(Decimal("1500"), "MW", source_unit="kW")
        self.assertEqual(result.value, Decimal("1.5"))

    def test_convert_with_int_value(self):
        result = convert(1500, "MW", source_unit="kW")
        self.assertEqual(result.value, Decimal("1.5"))

    def test_convert_different_dimensions_raises(self):
        reg = get_registry()
        w = reg.get("W")
        kwh = reg.get("kWh")
        q = Quantity(Decimal("100"), w)
        with self.assertRaises(ValueError):
            convert(q, kwh)

    def test_convert_preserves_sig_figs(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q = Quantity(Decimal("1500"), kw, sig_figs=3)
        result = convert(q, mw)
        self.assertEqual(result.sig_figs, 3)

    def test_convert_preserves_sig_figs_in_value(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        q = Quantity(Decimal("123456"), w, sig_figs=3)
        result = convert(q, kw)
        self.assertEqual(result.value, Decimal("123"))
        self.assertEqual(result.sig_figs, 3)


class TestTemperatureConversion(unittest.TestCase):
    def test_c_to_f_freezing(self):
        result = convert_temperature(0, "C", "F")
        self.assertAlmostEqual(float(result.value), 32.0, places=1)

    def test_c_to_f_boiling(self):
        result = convert_temperature(100, "C", "F")
        self.assertAlmostEqual(float(result.value), 212.0, places=1)

    def test_c_to_f_body_temp(self):
        result = convert_temperature(37, "C", "F")
        self.assertAlmostEqual(float(result.value), 98.6, places=1)

    def test_f_to_c_freezing(self):
        result = convert_temperature(32, "F", "C")
        self.assertAlmostEqual(float(result.value), 0.0, places=1)

    def test_f_to_c_boiling(self):
        result = convert_temperature(212, "F", "C")
        self.assertAlmostEqual(float(result.value), 100.0, places=1)

    def test_c_to_k(self):
        result = convert_temperature(0, "C", "K")
        self.assertAlmostEqual(float(result.value), 273.15, places=2)

    def test_k_to_c(self):
        result = convert_temperature(273.15, "K", "C")
        self.assertAlmostEqual(float(result.value), 0.0, places=2)

    def test_f_to_k(self):
        result = convert_temperature(32, "F", "K")
        self.assertAlmostEqual(float(result.value), 273.15, places=2)

    def test_c_to_f_with_sig_figs(self):
        result = convert_temperature(25, "C", "F", sig_figs=3)
        self.assertEqual(result.sig_figs, 3)

    def test_c_to_f_alias_scales(self):
        result = convert_temperature(100, "celsius", "fahrenheit")
        self.assertAlmostEqual(float(result.value), 212.0, places=1)

    def test_c_to_f_case_insensitive(self):
        result = convert_temperature(100, "c", "f")
        self.assertAlmostEqual(float(result.value), 212.0, places=1)

    def test_c_to_f_degree_symbol(self):
        result = convert_temperature(100, "°C", "°F")
        self.assertAlmostEqual(float(result.value), 212.0, places=1)

    def test_negative_c_to_f(self):
        result = convert_temperature(-40, "C", "F")
        self.assertAlmostEqual(float(result.value), -40.0, places=1)

    def test_c_to_f_preserves_sig_figs(self):
        result = convert_temperature(Decimal("25.12345"), "C", "F", sig_figs=4)
        self.assertEqual(result.sig_figs, 4)


class TestPowerFactorConversion(unittest.TestCase):
    def test_va_to_w(self):
        result = convert_with_power_factor(1000, "VA", "W", Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 900.0, places=1)

    def test_w_to_va(self):
        result = convert_with_power_factor(900, "W", "VA", Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 1000.0, places=1)

    def test_kva_to_kw(self):
        result = convert_with_power_factor(10, "kVA", "kW", Decimal("0.95"))
        self.assertAlmostEqual(float(result.value), 9.5, places=1)

    def test_kw_to_kva(self):
        result = convert_with_power_factor(9.5, "kW", "kVA", Decimal("0.95"))
        self.assertAlmostEqual(float(result.value), 10.0, places=1)

    def test_va_to_w_with_int_pf(self):
        result = convert_with_power_factor(1000, "VA", "W", 0.9)
        self.assertAlmostEqual(float(result.value), 900.0, places=1)

    def test_invalid_pf_zero(self):
        with self.assertRaises(ValueError):
            convert_with_power_factor(1000, "VA", "W", Decimal(0))

    def test_invalid_pf_negative(self):
        with self.assertRaises(ValueError):
            convert_with_power_factor(1000, "VA", "W", Decimal("-0.5"))

    def test_invalid_pf_greater_than_one(self):
        with self.assertRaises(ValueError):
            convert_with_power_factor(1000, "VA", "W", Decimal("1.1"))

    def test_pf_one(self):
        result = convert_with_power_factor(1000, "VA", "W", Decimal(1))
        self.assertAlmostEqual(float(result.value), 1000.0, places=1)

    def test_w_to_w_no_conversion(self):
        result = convert_with_power_factor(1000, "W", "W", Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 1000.0, places=1)

    def test_va_to_va_no_conversion(self):
        result = convert_with_power_factor(1000, "VA", "VA", Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 1000.0, places=1)

    def test_invalid_unit_combination(self):
        with self.assertRaises(ValueError):
            convert_with_power_factor(1000, "kW", "kWh", Decimal("0.9"))

    def test_sig_figs_with_pf(self):
        result = convert_with_power_factor(1000, "VA", "W", Decimal("0.9"), sig_figs=3)
        # PF 0.9 has 1 sig fig, so result is limited to 1
        self.assertEqual(result.sig_figs, 1)


class TestConvenienceFunctions(unittest.TestCase):
    def test_kw_to_mw(self):
        result = kw_to_mw(1500)
        self.assertEqual(result.value, Decimal("1.5"))
        self.assertEqual(result.unit.symbol, "MW")

    def test_mw_to_kw(self):
        result = mw_to_kw(1.5)
        self.assertEqual(result.value, Decimal("1500"))
        self.assertEqual(result.unit.symbol, "kW")

    def test_kwh_to_mwh(self):
        result = kwh_to_mwh(100)
        self.assertEqual(result.value, Decimal("0.1"))
        self.assertEqual(result.unit.symbol, "MWh")

    def test_mwh_to_kwh(self):
        result = mwh_to_kwh(0.1)
        self.assertEqual(result.value, Decimal("100"))
        self.assertEqual(result.unit.symbol, "kWh")

    def test_c_to_f(self):
        result = c_to_f(100)
        self.assertAlmostEqual(float(result.value), 212.0, places=1)

    def test_f_to_c(self):
        result = f_to_c(212)
        self.assertAlmostEqual(float(result.value), 100.0, places=1)

    def test_va_to_w(self):
        result = va_to_w(1000, Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 900.0, places=1)

    def test_w_to_va(self):
        result = w_to_va(900, Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 1000.0, places=1)

    def test_kva_to_kw(self):
        result = kva_to_kw(10, Decimal("0.95"))
        self.assertAlmostEqual(float(result.value), 9.5, places=1)

    def test_kw_to_kva(self):
        result = kw_to_kva(9.5, Decimal("0.95"))
        self.assertAlmostEqual(float(result.value), 10.0, places=1)

    def test_kw_to_mw_with_sig_figs(self):
        result = kw_to_mw(1500, sig_figs=3)
        self.assertEqual(result.sig_figs, 3)


class TestMakeQuantity(unittest.TestCase):
    def test_make_quantity_from_int(self):
        q = make_quantity(100, "kW")
        self.assertEqual(q.value, Decimal("100"))
        self.assertEqual(q.unit.symbol, "kW")

    def test_make_quantity_from_float(self):
        q = make_quantity(1.5, "MW")
        self.assertEqual(q.value, Decimal("1.5"))

    def test_make_quantity_from_string(self):
        q = make_quantity("1500.5", "kW")
        self.assertEqual(q.value, Decimal("1500.5"))

    def test_make_quantity_from_decimal(self):
        q = make_quantity(Decimal("100"), "kW")
        self.assertEqual(q.value, Decimal("100"))

    def test_make_quantity_with_sig_figs(self):
        q = make_quantity(100, "kW", sig_figs=3)
        self.assertEqual(q.sig_figs, 3)

    def test_make_quantity_invalid_type(self):
        with self.assertRaises(TypeError):
            make_quantity("not_a_number", "kW")

    def test_make_quantity_unknown_unit(self):
        with self.assertRaises(KeyError):
            make_quantity(100, "unknown")


class TestFormatQuantity(unittest.TestCase):
    def test_format_basic(self):
        q = make_quantity(1500, "kW")
        s = format_quantity(q)
        self.assertIn("1500", s)
        self.assertIn("kW", s)

    def test_format_with_decimal_places(self):
        q = make_quantity(Decimal("1.23456"), "kW")
        s = format_quantity(q, decimal_places=2)
        self.assertIn("1.23", s)

    def test_format_si_prefix_power(self):
        q = make_quantity(1500, "kW")
        s = format_quantity(q, use_si_prefix=True)
        self.assertIn("MW", s)

    def test_format_si_prefix_energy(self):
        q = make_quantity(1500, "kWh")
        s = format_quantity(q, use_si_prefix=True)
        self.assertIn("MWh", s)

    def test_format_si_prefix_small_value(self):
        q = make_quantity(500, "W")
        s = format_quantity(q, use_si_prefix=True)
        self.assertIn("W", s)


class TestComputeFunctions(unittest.TestCase):
    def test_compute_pue(self):
        result = compute_pue(Decimal("1000"), Decimal("800"))
        self.assertAlmostEqual(float(result), 1.25, places=2)

    def test_compute_pue_with_int(self):
        result = compute_pue(1000, 800)
        self.assertAlmostEqual(float(result), 1.25, places=2)

    def test_compute_pue_zero_it_power(self):
        with self.assertRaises(ValueError):
            compute_pue(Decimal("1000"), Decimal(0))

    def test_compute_pue_with_sig_figs(self):
        result = compute_pue(Decimal("1000"), Decimal("800"), sig_figs=3)
        self.assertAlmostEqual(float(result), 1.25, places=2)

    def test_compute_dcime(self):
        result = compute_dcime(Decimal("800"), Decimal("1000"))
        self.assertAlmostEqual(float(result), 0.8, places=2)

    def test_compute_dcime_zero_total(self):
        with self.assertRaises(ValueError):
            compute_dcime(Decimal("800"), Decimal(0))

    def test_compute_carbon_emissions(self):
        result = compute_carbon_emissions(Decimal("1000"), Decimal("0.5"))
        self.assertEqual(result.value, Decimal("500"))
        self.assertEqual(result.unit.symbol, "kg")

    def test_compute_carbon_emissions_with_int(self):
        result = compute_carbon_emissions(1000, 0.5)
        self.assertEqual(result.value, Decimal("500"))

    def test_compute_energy_from_power(self):
        reg = get_registry()
        kw = reg.get("kW")
        power = Quantity(Decimal("10"), kw)
        result = compute_energy_from_power(power, Decimal("5"))
        self.assertEqual(result.value, Decimal("50"))
        self.assertEqual(result.unit.symbol, "kWh")

    def test_compute_energy_from_power_zero_duration(self):
        reg = get_registry()
        kw = reg.get("kW")
        power = Quantity(Decimal("10"), kw)
        result = compute_energy_from_power(power, Decimal(0))
        self.assertEqual(result.value, Decimal(0))

    def test_compute_energy_from_power_negative_duration(self):
        reg = get_registry()
        kw = reg.get("kW")
        power = Quantity(Decimal("10"), kw)
        with self.assertRaises(ValueError):
            compute_energy_from_power(power, Decimal("-1"))

    def test_compute_power_from_energy(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        energy = Quantity(Decimal("50"), kwh)
        result = compute_power_from_energy(energy, Decimal("5"))
        self.assertEqual(result.value, Decimal("10"))
        self.assertEqual(result.unit.symbol, "kW")

    def test_compute_power_from_energy_zero_duration(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        energy = Quantity(Decimal("50"), kwh)
        with self.assertRaises(ValueError):
            compute_power_from_energy(energy, Decimal(0))

    def test_compute_cooling_load(self):
        result = compute_cooling_load(Decimal("100"), Decimal("4"))
        # 100/4=25, but both inputs have 1 sig fig so result rounds to 30
        self.assertEqual(result.value, Decimal("3E+1"))
        self.assertEqual(result.unit.symbol, "kW")

    def test_compute_cooling_load_zero_cop(self):
        with self.assertRaises(ValueError):
            compute_cooling_load(Decimal("100"), Decimal(0))

    def test_compute_cooling_load_negative_cop(self):
        with self.assertRaises(ValueError):
            compute_cooling_load(Decimal("100"), Decimal("-1"))

    def test_compute_ups_runtime(self):
        result = compute_ups_runtime(Decimal("100"), Decimal("10"))
        self.assertAlmostEqual(float(result.value), 10.0, places=1)
        self.assertEqual(result.unit.symbol, "h")

    def test_compute_ups_runtime_custom_efficiency(self):
        result = compute_ups_runtime(Decimal("100"), Decimal("10"), efficiency=Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), Decimal("9"), places=1)

    def test_compute_ups_runtime_zero_load(self):
        with self.assertRaises(ValueError):
            compute_ups_runtime(Decimal("100"), Decimal(0))

    def test_compute_ups_runtime_invalid_efficiency(self):
        with self.assertRaises(ValueError):
            compute_ups_runtime(Decimal("100"), Decimal("10"), efficiency=Decimal("0"))

    def test_compute_ups_runtime_efficiency_greater_than_one(self):
        with self.assertRaises(ValueError):
            compute_ups_runtime(Decimal("100"), Decimal("10"), efficiency=Decimal("1.1"))


class TestBatchOperations(unittest.TestCase):
    def test_convert_many(self):
        reg = get_registry()
        kw = reg.get("kW")
        quantities = [
            Quantity(Decimal("1000"), kw),
            Quantity(Decimal("2000"), kw),
            Quantity(Decimal("3000"), kw),
        ]
        results = convert_many(quantities, "MW")
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0].value, Decimal("1"))
        self.assertEqual(results[1].value, Decimal("2"))
        self.assertEqual(results[2].value, Decimal("3"))

    def test_normalize_to_base(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        quantities = [
            Quantity(Decimal("1"), kw),
            Quantity(Decimal("1"), mw),
        ]
        results = normalize_to_base(quantities)
        self.assertEqual(results[0].value, Decimal("1000"))
        self.assertEqual(results[0].unit.symbol, "W")
        self.assertEqual(results[1].value, Decimal("1000000"))
        self.assertEqual(results[1].unit.symbol, "W")


class TestValidationHelpers(unittest.TestCase):
    def test_validate_same_dimension_true(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q1 = Quantity(Decimal("1"), kw)
        q2 = Quantity(Decimal("1"), mw)
        self.assertTrue(validate_same_dimension(q1, q2))

    def test_validate_same_dimension_false(self):
        reg = get_registry()
        kw = reg.get("kW")
        kwh = reg.get("kWh")
        q1 = Quantity(Decimal("1"), kw)
        q2 = Quantity(Decimal("1"), kwh)
        self.assertFalse(validate_same_dimension(q1, q2))

    def test_validate_same_dimension_empty(self):
        self.assertTrue(validate_same_dimension())

    def test_assert_same_dimension_passes(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q1 = Quantity(Decimal("1"), kw)
        q2 = Quantity(Decimal("1"), mw)
        assert_same_dimension(q1, q2)  # Should not raise

    def test_assert_same_dimension_raises(self):
        reg = get_registry()
        kw = reg.get("kW")
        kwh = reg.get("kWh")
        q1 = Quantity(Decimal("1"), kw)
        q2 = Quantity(Decimal("1"), kwh)
        with self.assertRaises(ValueError):
            assert_same_dimension(q1, q2)

    def test_validate_range_within(self):
        reg = get_registry()
        kw = reg.get("kW")
        q = Quantity(Decimal("500"), kw)
        self.assertTrue(validate_range(q, min_value=Decimal(0), max_value=Decimal(1000)))

    def test_validate_range_below_min(self):
        reg = get_registry()
        kw = reg.get("kW")
        q = Quantity(Decimal("-1"), kw)
        self.assertFalse(validate_range(q, min_value=Decimal(0)))

    def test_validate_range_above_max(self):
        reg = get_registry()
        kw = reg.get("kW")
        q = Quantity(Decimal("1001"), kw)
        self.assertFalse(validate_range(q, max_value=Decimal(1000)))

    def test_validate_range_no_bounds(self):
        reg = get_registry()
        kw = reg.get("kW")
        q = Quantity(Decimal("500"), kw)
        self.assertTrue(validate_range(q))

    def test_validate_range_with_int_bounds(self):
        reg = get_registry()
        kw = reg.get("kW")
        q = Quantity(Decimal("500"), kw)
        self.assertTrue(validate_range(q, min_value=0, max_value=1000))


class TestSigFigTracking(unittest.TestCase):
    def test_count_sig_figs(self):
        from dcc.validation.units import _count_sig_figs
        self.assertEqual(_count_sig_figs(Decimal("100")), 1)
        self.assertEqual(_count_sig_figs(Decimal("1000")), 1)
        self.assertEqual(_count_sig_figs(Decimal("100.0")), 4)
        self.assertEqual(_count_sig_figs(Decimal("0.001")), 1)
        self.assertEqual(_count_sig_figs(Decimal("0")), None)

    def test_apply_sig_figs(self):
        from dcc.validation.units import _apply_sig_figs
        self.assertEqual(_apply_sig_figs(Decimal("12345"), 3), Decimal("12300"))
        self.assertEqual(_apply_sig_figs(Decimal("0.0012345"), 3), Decimal("0.00123"))

    def test_mul_sig_figs(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w, sig_figs=3)
        result = q * Decimal("2.5")
        self.assertEqual(result.sig_figs, 2)

    def test_div_sig_figs(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w, sig_figs=3)
        result = q / Decimal("2.5")
        self.assertEqual(result.sig_figs, 2)

    def test_add_loses_sig_figs(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("100"), w, sig_figs=3)
        q2 = Quantity(Decimal("200"), w, sig_figs=3)
        result = q1 + q2
        self.assertIsNone(result.sig_figs)


class TestEdgeCases(unittest.TestCase):
    def test_zero_value_conversion(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q = Quantity(Decimal(0), kw)
        result = convert(q, mw)
        self.assertEqual(result.value, Decimal(0))

    def test_very_large_value(self):
        reg = get_registry()
        w = reg.get("W")
        gw = reg.get("GW")
        q = Quantity(Decimal("1000000000000"), w)
        result = convert(q, gw)
        self.assertEqual(result.value, Decimal("1000"))

    def test_very_small_value(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        q = Quantity(Decimal("0.000001"), w)
        result = convert(q, kw)
        self.assertAlmostEqual(float(result.value), 0.000000001, places=12)

    def test_va_to_kva(self):
        result = va_to_kva(1000, Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 1.0, places=1)

    def test_negative_power(self):
        reg = get_registry()
        kw = reg.get("kW")
        mw = reg.get("MW")
        q = Quantity(Decimal("-1500"), kw)
        result = convert(q, mw)
        self.assertEqual(result.value, Decimal("-1.5"))

    def test_negative_energy(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        mwh = reg.get("MWh")
        q = Quantity(Decimal("-100"), kwh)
        result = convert(q, mwh)
        self.assertEqual(result.value, Decimal("-0.1"))

    def test_temperature_negative_c_to_f(self):
        result = convert_temperature(-40, "C", "F")
        self.assertAlmostEqual(float(result.value), -40.0, places=1)

    def test_temperature_very_hot(self):
        result = convert_temperature(1000, "C", "F")
        self.assertAlmostEqual(float(result.value), 1832.0, places=1)

    def test_pressure_psi_to_bar(self):
        reg = get_registry()
        psi = reg.get("psi")
        bar = reg.get("bar")
        q = Quantity(Decimal("14.5038"), psi)
        result = convert(q, bar)
        self.assertAlmostEqual(float(result.value), 1.0, places=2)

    def test_flow_cfm_to_m3h(self):
        reg = get_registry()
        cfm = reg.get("CFM")
        m3h = reg.get("m³/h")
        q = Quantity(Decimal("1000"), cfm)
        result = convert(q, m3h)
        self.assertAlmostEqual(float(result.value), 1699.0, places=0)

    def test_data_gb_to_mb(self):
        reg = get_registry()
        gb = reg.get("GB")
        mb = reg.get("MB")
        q = Quantity(Decimal("1.5"), gb)
        result = convert(q, mb)
        self.assertEqual(result.value, Decimal("1500"))

    def test_data_gib_to_gb(self):
        reg = get_registry()
        gib = reg.get("GiB")
        gb = reg.get("GB")
        q = Quantity(Decimal("1"), gib)
        result = convert(q, gb)
        self.assertAlmostEqual(float(result.value), 1.073741824, places=6)

    def test_carbon_g_to_kg(self):
        reg = get_registry()
        g = reg.get("g/kWh")
        kg = reg.get("kg/kWh")
        q = Quantity(Decimal("500"), g)
        result = convert(q, kg)
        self.assertEqual(result.value, Decimal("0.5"))

    def test_efficiency_percent_to_ratio(self):
        reg = get_registry()
        pct = reg.get("%")
        ratio = reg.get("η")
        q = Quantity(Decimal("95"), pct)
        result = convert(q, ratio)
        self.assertEqual(result.value, Decimal("0.95"))

    def test_length_ft_to_m(self):
        reg = get_registry()
        ft = reg.get("ft")
        m = reg.get("m")
        q = Quantity(Decimal("10"), ft)
        result = convert(q, m)
        self.assertEqual(result.value, Decimal("3.048"))

    def test_area_ft2_to_m2(self):
        reg = get_registry()
        ft2 = reg.get("ft²")
        m2 = reg.get("m²")
        q = Quantity(Decimal("100"), ft2)
        result = convert(q, m2)
        self.assertEqual(result.value, Decimal("9.290304"))

    def test_volume_l_to_m3(self):
        reg = get_registry()
        l = reg.get("L")
        m3 = reg.get("m³")
        q = Quantity(Decimal("1000"), l)
        result = convert(q, m3)
        self.assertEqual(result.value, Decimal("1"))

    def test_mass_lb_to_kg(self):
        reg = get_registry()
        lb = reg.get("lb")
        kg = reg.get("kg")
        q = Quantity(Decimal("1"), lb)
        result = convert(q, kg)
        self.assertEqual(result.value, Decimal("0.45359237"))

    def test_time_h_to_s(self):
        reg = get_registry()
        h = reg.get("h")
        s = reg.get("s")
        q = Quantity(Decimal("1"), h)
        result = convert(q, s)
        self.assertEqual(result.value, Decimal("3600"))

    def test_frequency_mhz_to_hz(self):
        reg = get_registry()
        mhz = reg.get("MHz")
        hz = reg.get("Hz")
        q = Quantity(Decimal("2.4"), mhz)
        result = convert(q, hz)
        self.assertEqual(result.value, Decimal("2400000"))

    def test_current_a_to_ma(self):
        reg = get_registry()
        a = reg.get("A")
        ma = reg.get("mA")
        q = Quantity(Decimal("1"), a)
        result = convert(q, ma)
        self.assertEqual(result.value, Decimal("1000"))

    def test_voltage_v_to_mv(self):
        reg = get_registry()
        v = reg.get("V")
        mv = reg.get("mV")
        q = Quantity(Decimal("1"), v)
        result = convert(q, mv)
        self.assertEqual(result.value, Decimal("1000"))

    def test_energy_btu_to_kwh(self):
        reg = get_registry()
        btu = reg.get("BTU")
        kwh = reg.get("kWh")
        q = Quantity(Decimal("3412.14"), btu)
        result = convert(q, kwh)
        self.assertAlmostEqual(float(result.value), 1.0, places=2)

    def test_power_hp_to_kw(self):
        reg = get_registry()
        hp = reg.get("hp")
        kw = reg.get("kW")
        q = Quantity(Decimal("1"), hp)
        result = convert(q, kw)
        self.assertAlmostEqual(float(result.value), 0.745699872, places=6)

    def test_power_rt_to_kw(self):
        reg = get_registry()
        rt = reg.get("RT")
        kw = reg.get("kW")
        q = Quantity(Decimal("1"), rt)
        result = convert(q, kw)
        self.assertAlmostEqual(float(result.value), 3.51685284, places=6)


class TestRegistryCompleteness(unittest.TestCase):
    def test_all_dimensions_have_base_units(self):
        reg = get_registry()
        for dim in Dimension:
            if dim == Dimension.CURRENCY:
                continue  # Currency has no meaningful base
            try:
                base = reg.get_base_unit(dim)
                self.assertIsNotNone(base)
            except KeyError:
                self.fail(f"No base unit for {dim.value}")

    def test_power_units_exist(self):
        reg = get_registry()
        for sym in ("W", "kW", "MW", "GW", "VA", "kVA", "MVA"):
            self.assertIsNotNone(reg.get(sym))

    def test_energy_units_exist(self):
        reg = get_registry()
        for sym in ("Wh", "kWh", "MWh", "GWh", "J", "kJ", "MJ", "GJ", "BTU"):
            self.assertIsNotNone(reg.get(sym))

    def test_temperature_units_exist(self):
        reg = get_registry()
        for sym in ("K", "°C", "°F", "°R"):
            self.assertIsNotNone(reg.get(sym))

    def test_pressure_units_exist(self):
        reg = get_registry()
        for sym in ("Pa", "kPa", "MPa", "bar", "mbar", "psi", "inH2O", "inHg", "atm"):
            self.assertIsNotNone(reg.get(sym))

    def test_flow_units_exist(self):
        reg = get_registry()
        for sym in ("m³/s", "m³/h", "m³/min", "L/s", "L/min", "GPM", "CFM", "ft³/s"):
            self.assertIsNotNone(reg.get(sym))

    def test_length_units_exist(self):
        reg = get_registry()
        for sym in ("m", "km", "cm", "mm", "ft", "in", "mi", "yd"):
            self.assertIsNotNone(reg.get(sym))

    def test_area_units_exist(self):
        reg = get_registry()
        for sym in ("m²", "ft²", "km²", "ac", "ha"):
            self.assertIsNotNone(reg.get(sym))

    def test_volume_units_exist(self):
        reg = get_registry()
        for sym in ("m³", "L", "mL", "gal", "ft³"):
            self.assertIsNotNone(reg.get(sym))

    def test_mass_units_exist(self):
        reg = get_registry()
        for sym in ("kg", "g", "t", "lb", "oz"):
            self.assertIsNotNone(reg.get(sym))

    def test_time_units_exist(self):
        reg = get_registry()
        for sym in ("s", "min", "h", "d", "wk", "mo", "yr"):
            self.assertIsNotNone(reg.get(sym))

    def test_data_units_exist(self):
        reg = get_registry()
        for sym in ("B", "kB", "MB", "GB", "TB", "PB", "KiB", "MiB", "GiB", "TiB"):
            self.assertIsNotNone(reg.get(sym))

    def test_carbon_units_exist(self):
        reg = get_registry()
        for sym in ("kg/kWh", "g/kWh", "kg/MWh", "lb/MWh"):
            self.assertIsNotNone(reg.get(sym))

    def test_efficiency_units_exist(self):
        reg = get_registry()
        for sym in ("η", "%", "PUE", "DCIE"):
            self.assertIsNotNone(reg.get(sym))


if __name__ == "__main__":
    unittest.main()
