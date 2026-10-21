"""Unit tests for dcc.validation.units module."""
import unittest
from decimal import Decimal

from dcc.validation.units import (
    Dimension,
    Unit,
    Quantity,
    UnitRegistry,
    get_registry,
    convert,
    convert_temperature,
    convert_with_power_factor,
    make_quantity,
    format_quantity,
    kw_to_mw,
    mw_to_kw,
    kwh_to_mwh,
    mwh_to_kwh,
    c_to_f,
    f_to_c,
    va_to_w,
    w_to_va,
    kva_to_kw,
    kw_to_kva,
    va_to_kva,
    compute_pue,
    compute_dcime,
    compute_carbon_emissions,
    compute_energy_from_power,
    compute_power_from_energy,
    compute_cooling_load,
    compute_ups_runtime,
    convert_many,
    normalize_to_base,
    validate_same_dimension,
    validate_range,
    assert_same_dimension,
)


class TestDimension(unittest.TestCase):
    def test_dimension_values(self):
        self.assertEqual(Dimension.POWER.value, "power")
        self.assertEqual(Dimension.ENERGY.value, "energy")
        self.assertEqual(Dimension.TEMPERATURE.value, "temperature")
        self.assertEqual(Dimension.PRESSURE.value, "pressure")
        self.assertEqual(Dimension.FLOW.value, "flow")

    def test_dimension_enum_members(self):
        self.assertGreater(len(Dimension), 10)


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
        # Decimal(273.15) takes a FLOAT and yields 273.14999999999997726...; the string
        # form is exact. The production registry had this same mistake and returned an
        # offset that did not round-trip to 273.15.
        u = Unit("celsius", "°C", Dimension.TEMPERATURE, Decimal(1), Decimal("273.15"))
        self.assertEqual(u.offset, Decimal("273.15"))


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
        q = Quantity(Decimal("100"), w)
        self.assertIn("100", repr(q))

    def test_quantity_str(self):
        reg = get_registry()
        w = reg.get("W")
        q = Quantity(Decimal("100"), w)
        self.assertIn("100", str(q))

    def test_quantity_equality(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("100"), w)
        self.assertEqual(q1, q2)

    def test_quantity_inequality(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("200"), w)
        self.assertNotEqual(q1, q2)

    def test_quantity_addition(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("200"), w)
        result = q1 + q2
        self.assertEqual(result.value, Decimal("300"))

    def test_quantity_addition_different_dimensions(self):
        reg = get_registry()
        w = reg.get("W")
        kwh = reg.get("kWh")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("200"), kwh)
        with self.assertRaises(ValueError):
            q1 + q2

    def test_quantity_subtraction(self):
        reg = get_registry()
        w = reg.get("W")
        q1 = Quantity(Decimal("200"), w)
        q2 = Quantity(Decimal("100"), w)
        result = q1 - q2
        self.assertEqual(result.value, Decimal("100"))


class TestUnitRegistry(unittest.TestCase):
    def test_get_registry(self):
        reg = get_registry()
        self.assertIsInstance(reg, UnitRegistry)

    def test_get_unit(self):
        reg = get_registry()
        w = reg.get("W")
        self.assertIsNotNone(w)
        self.assertEqual(w.symbol, "W")

    def test_get_kwh(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        self.assertIsNotNone(kwh)

    def test_list_units(self):
        reg = get_registry()
        units = reg.list_units()
        self.assertGreater(len(units), 0)

    def test_get_base_unit(self):
        reg = get_registry()
        base = reg.get_base_unit(Dimension.POWER)
        self.assertIsNotNone(base)


class TestConvert(unittest.TestCase):
    def test_convert_w_to_kw(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        q = Quantity(Decimal("1000"), w)
        result = convert(q, kw)
        self.assertAlmostEqual(float(result.value), 1.0)

    def test_convert_kwh_to_mwh(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        mwh = reg.get("MWh")
        q = Quantity(Decimal("1000"), kwh)
        result = convert(q, mwh)
        self.assertAlmostEqual(float(result.value), 1.0)


class TestConvertTemperature(unittest.TestCase):
    def test_c_to_f(self):
        result = convert_temperature(Decimal("0"), "C", "F")
        self.assertAlmostEqual(float(result.value), 32.0)

    def test_f_to_c(self):
        result = convert_temperature(Decimal("32"), "F", "C")
        self.assertAlmostEqual(float(result.value), 0.0)

    def test_c_to_k(self):
        result = convert_temperature(Decimal("0"), "C", "K")
        self.assertAlmostEqual(float(result.value), 273.15)


class TestConvertWithPowerFactor(unittest.TestCase):
    def test_kw_to_kva(self):
        # 100 kW of real power at power factor 0.9 draws 100 / 0.9 = 111.1 kVA of
        # apparent power. This assertion is correct; the conversion function was not
        # applying the power factor for a kW -> kVA conversion.
        result = convert_with_power_factor(Decimal("100"), "kW", "kVA", Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 100.0 / 0.9, places=4)

    def test_kva_to_kw(self):
        result = convert_with_power_factor(Decimal("100"), "kVA", "kW", Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 90.0)


class TestMakeQuantity(unittest.TestCase):
    def test_make_quantity(self):
        q = make_quantity(Decimal("100"), "W")
        self.assertEqual(q.value, Decimal("100"))
        self.assertEqual(q.unit.symbol, "W")

    def test_make_quantity_with_sig_figs(self):
        q = make_quantity(Decimal("100"), "W", sig_figs=3)
        self.assertEqual(q.sig_figs, 3)


class TestFormatQuantity(unittest.TestCase):
    def test_format(self):
        q = make_quantity(Decimal("100"), "W")
        s = format_quantity(q)
        self.assertIn("100", s)

    def test_format_with_decimal_places(self):
        q = make_quantity(Decimal("100.123456"), "W")
        s = format_quantity(q, decimal_places=2)
        self.assertIn("100.12", s)


class TestKwToMw(unittest.TestCase):
    def test_basic(self):
        result = kw_to_mw(Decimal("1000"))
        self.assertAlmostEqual(float(result.value), 1.0)


class TestMwToKw(unittest.TestCase):
    def test_basic(self):
        result = mw_to_kw(Decimal("1"))
        self.assertAlmostEqual(float(result.value), 1000.0)


class TestKwhToMwh(unittest.TestCase):
    def test_basic(self):
        result = kwh_to_mwh(Decimal("1000"))
        self.assertAlmostEqual(float(result.value), 1.0)


class TestMwhToKwh(unittest.TestCase):
    def test_basic(self):
        result = mwh_to_kwh(Decimal("1"))
        self.assertAlmostEqual(float(result.value), 1000.0)


class TestCToF(unittest.TestCase):
    def test_freezing(self):
        result = c_to_f(Decimal("0"))
        self.assertAlmostEqual(float(result.value), 32.0)

    def test_boiling(self):
        result = c_to_f(Decimal("100"))
        self.assertAlmostEqual(float(result.value), 212.0)


class TestFToC(unittest.TestCase):
    def test_freezing(self):
        result = f_to_c(Decimal("32"))
        self.assertAlmostEqual(float(result.value), 0.0)

    def test_boiling(self):
        result = f_to_c(Decimal("212"))
        self.assertAlmostEqual(float(result.value), 100.0)


class TestVaToW(unittest.TestCase):
    def test_basic(self):
        result = va_to_w(Decimal("100"), Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 90.0)


class TestWToVa(unittest.TestCase):
    def test_basic(self):
        result = w_to_va(Decimal("90"), Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 100.0)


class TestKvaToKw(unittest.TestCase):
    def test_basic(self):
        result = kva_to_kw(Decimal("100"), Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 90.0)


class TestKwToKva(unittest.TestCase):
    def test_basic(self):
        result = kw_to_kva(Decimal("90"), Decimal("0.9"))
        self.assertAlmostEqual(float(result.value), 100.0)


class TestVaToKva(unittest.TestCase):
    def test_basic(self):
        result = va_to_kva(Decimal("100"), Decimal("0.9"))
        # 100 VA == 0.1 kVA. The previous expectation (100/0.9) applied the power
        # factor as if converting VA->W, but VA->kVA is a pure unit prefix change;
        # the power factor is irrelevant. The function was right.
        self.assertAlmostEqual(float(result.value), 0.1)


class TestComputePue(unittest.TestCase):
    def test_basic(self):
        result = compute_pue(Decimal("150"), Decimal("100"))
        self.assertAlmostEqual(float(result), 1.5)


class TestComputeDcime(unittest.TestCase):
    def test_basic(self):
        result = compute_dcime(Decimal("100"), Decimal("150"))
        self.assertAlmostEqual(float(result), 100.0 / 150.0)


class TestComputeCarbonEmissions(unittest.TestCase):
    def test_basic(self):
        result = compute_carbon_emissions(Decimal("1000"), Decimal("0.5"))
        self.assertAlmostEqual(float(result.value), 500.0)


class TestComputeEnergyFromPower(unittest.TestCase):
    def test_basic(self):
        reg = get_registry()
        kw = reg.get("kW")
        power = Quantity(Decimal("10"), kw)
        result = compute_energy_from_power(power, Decimal("5"))
        self.assertAlmostEqual(float(result.value), 50.0)


class TestComputePowerFromEnergy(unittest.TestCase):
    def test_basic(self):
        reg = get_registry()
        kwh = reg.get("kWh")
        energy = Quantity(Decimal("50"), kwh)
        result = compute_power_from_energy(energy, Decimal("5"))
        self.assertAlmostEqual(float(result.value), 10.0)


class TestComputeCoolingLoad(unittest.TestCase):
    def test_basic(self):
        result = compute_cooling_load(Decimal("100"), Decimal("3"))
        self.assertAlmostEqual(float(result.value), 100.0 / 3.0)


class TestComputeUpsRuntime(unittest.TestCase):
    def test_basic(self):
        result = compute_ups_runtime(Decimal("100"), Decimal("50"))
        self.assertGreater(float(result.value), 0)


class TestConvertMany(unittest.TestCase):
    def test_convert_many(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        quantities = [Quantity(Decimal("1000"), w), Quantity(Decimal("2000"), w)]
        result = convert_many(quantities, kw)
        self.assertEqual(len(result), 2)
        self.assertAlmostEqual(float(result[0].value), 1.0)


class TestNormalizeToBase(unittest.TestCase):
    def test_normalize(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        quantities = [Quantity(Decimal("1000"), w), Quantity(Decimal("1"), kw)]
        result = normalize_to_base(quantities)
        self.assertEqual(len(result), 2)


class TestValidateSameDimension(unittest.TestCase):
    def test_same_dimension(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("1"), kw)
        self.assertTrue(validate_same_dimension(q1, q2))

    def test_different_dimension(self):
        reg = get_registry()
        w = reg.get("W")
        kwh = reg.get("kWh")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("1"), kwh)
        self.assertFalse(validate_same_dimension(q1, q2))


class TestValidateRange(unittest.TestCase):
    def test_in_range(self):
        q = make_quantity(Decimal("50"), "W")
        self.assertTrue(validate_range(q, min_value=Decimal("0"), max_value=Decimal("100")))

    def test_out_of_range(self):
        q = make_quantity(Decimal("150"), "W")
        self.assertFalse(validate_range(q, min_value=Decimal("0"), max_value=Decimal("100")))


class TestAssertSameDimension(unittest.TestCase):
    def test_assert_same(self):
        reg = get_registry()
        w = reg.get("W")
        kw = reg.get("kW")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("1"), kw)
        assert_same_dimension(q1, q2)

    def test_assert_different(self):
        reg = get_registry()
        w = reg.get("W")
        kwh = reg.get("kWh")
        q1 = Quantity(Decimal("100"), w)
        q2 = Quantity(Decimal("1"), kwh)
        with self.assertRaises(ValueError):
            assert_same_dimension(q1, q2)


if __name__ == "__main__":
    unittest.main()
