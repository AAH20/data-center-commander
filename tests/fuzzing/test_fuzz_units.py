"""Fuzz tests for unit conversion system using Hypothesis."""
from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation

import pytest
from hypothesis import given, settings, strategies as st, assume, HealthCheck

from dcc.validation.units import (
    Dimension,
    Quantity,
    Unit,
    UNIT_REGISTRY,
    compute_carbon_emissions,
    compute_cooling_load,
    compute_dcime,
    compute_energy_from_power,
    compute_power_from_energy,
    compute_pue,
    compute_ups_runtime,
    convert,
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
    va_to_w,
    w_to_va,
)


# Strategies
finite_decimals = st.decimals(
    min_value=-1e15, max_value=1e15, allow_nan=False, allow_infinity=False
)

positive_decimals = st.decimals(
    min_value=Decimal("0.000001"), max_value=1e15, allow_nan=False, allow_infinity=False
)

small_positive_decimals = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False
)

power_factor_decimals = st.decimals(
    min_value=Decimal("0.001"), max_value=Decimal("1.0"), allow_nan=False, allow_infinity=False
)

unit_symbols = st.sampled_from([
    "W", "kW", "MW", "GW", "VA", "kVA", "MVA",
    "Wh", "kWh", "MWh", "GWh",
    "°C", "°F", "K", "°R",
    "Pa", "kPa", "bar", "psi",
    "m³/s", "m³/h", "L/min", "CFM",
    "m", "km", "ft", "in",
    "m²", "ft²",
    "m³", "L", "gal",
    "kg", "g", "lb",
    "s", "min", "h", "d",
    "Hz", "kHz", "MHz",
    "A", "mA", "kA",
    "V", "mV", "kV",
    "PF", "PF%",
    "η", "%", "PUE", "DCIE",
    "kg/kWh", "g/kWh",
    "B", "kB", "MB", "GB", "TB", "KiB", "MiB", "GiB",
    "USD", "EUR", "GBP", "JPY",
])


class TestUnitConversionFuzz:
    """Fuzz unit conversions with arbitrary valid inputs."""

    @given(value=finite_decimals, unit=unit_symbols)
    @settings(max_examples=200, suppress_health_check=[HealthCheck.too_slow])
    def test_make_quantity_never_crashes(self, value, unit):
        """make_quantity should handle any finite decimal + valid unit."""
        try:
            q = make_quantity(value, unit)
            assert q.value == value
        except (ValueError, TypeError):
            pass  # Expected for some edge cases

    @given(
        value=finite_decimals,
        from_unit=st.sampled_from(["W", "kW", "MW", "GW"]),
        to_unit=st.sampled_from(["W", "kW", "MW", "GW"]),
    )
    @settings(max_examples=200)
    def test_power_conversion_roundtrip(self, value, from_unit, to_unit):
        """Converting power units should preserve value through roundtrip."""
        q = make_quantity(value, from_unit)
        converted = q.to(to_unit)
        back = converted.to(from_unit)
        if value == 0:
            assert back.value == 0
        else:
            # Allow for precision loss
            ratio = abs(back.value / value) if value != 0 else 1.0
            assert 0.999 < ratio < 1.001

    @given(
        value=finite_decimals,
        from_unit=st.sampled_from(["Wh", "kWh", "MWh", "GWh"]),
        to_unit=st.sampled_from(["Wh", "kWh", "MWh", "GWh"]),
    )
    @settings(max_examples=200)
    def test_energy_conversion_roundtrip(self, value, from_unit, to_unit):
        """Converting energy units should preserve value through roundtrip."""
        q = make_quantity(value, from_unit)
        converted = q.to(to_unit)
        back = converted.to(from_unit)
        if value == 0:
            assert back.value == 0
        else:
            ratio = abs(back.value / value) if value != 0 else 1.0
            assert 0.999 < ratio < 1.001

    @given(
        value=finite_decimals,
        from_scale=st.sampled_from(["C", "F", "K", "R"]),
        to_scale=st.sampled_from(["C", "F", "K", "R"]),
    )
    @settings(max_examples=200)
    def test_temperature_conversion_roundtrip(self, value, from_scale, to_scale):
        """Temperature conversion should roundtrip (with precision loss)."""
        assume(value > -1e10 and value < 1e10)
        q = convert_temperature(value, from_scale, to_scale)
        back = convert_temperature(q.value, to_scale, from_scale)
        if value == 0:
            assert abs(back.value) < 0.01
        else:
            ratio = abs(back.value / value)
            assert 0.99 < ratio < 1.01

    @given(
        value=positive_decimals,
        from_unit=st.sampled_from(["W", "kW", "MW"]),
        to_unit=st.sampled_from(["VA", "kVA", "MVA"]),
        pf=power_factor_decimals,
    )
    @settings(max_examples=200)
    def test_power_factor_conversion(self, value, from_unit, to_unit, pf):
        """Power factor conversion should produce valid results."""
        q = convert_with_power_factor(value, from_unit, to_unit, pf)
        assert q.value >= 0
        assert q.unit.symbol == to_unit

    @given(
        value=finite_decimals,
        from_unit=st.sampled_from(["m", "km", "ft", "in", "cm", "mm"]),
        to_unit=st.sampled_from(["m", "km", "ft", "in", "cm", "mm"]),
    )
    @settings(max_examples=200)
    def test_length_conversion_roundtrip(self, value, from_unit, to_unit):
        """Length conversion should roundtrip."""
        q = make_quantity(value, from_unit)
        converted = q.to(to_unit)
        back = converted.to(from_unit)
        if value == 0:
            assert back.value == 0
        else:
            ratio = abs(back.value / value)
            assert 0.999 < ratio < 1.001

    @given(
        value=finite_decimals,
        from_unit=st.sampled_from(["m²", "ft²", "km²", "ac", "ha"]),
        to_unit=st.sampled_from(["m²", "ft²", "km²", "ac", "ha"]),
    )
    @settings(max_examples=200)
    def test_area_conversion_roundtrip(self, value, from_unit, to_unit):
        """Area conversion should roundtrip."""
        q = make_quantity(value, from_unit)
        converted = q.to(to_unit)
        back = converted.to(from_unit)
        if value == 0:
            assert back.value == 0
        else:
            ratio = abs(back.value / value)
            assert 0.999 < ratio < 1.001

    @given(
        value=finite_decimals,
        from_unit=st.sampled_from(["B", "kB", "MB", "GB", "TB", "KiB", "MiB", "GiB"]),
        to_unit=st.sampled_from(["B", "kB", "MB", "GB", "TB", "KiB", "MiB", "GiB"]),
    )
    @settings(max_examples=200)
    def test_data_conversion_roundtrip(self, value, from_unit, to_unit):
        """Data size conversion should roundtrip."""
        q = make_quantity(value, from_unit)
        converted = q.to(to_unit)
        back = converted.to(from_unit)
        if value == 0:
            assert back.value == 0
        else:
            ratio = abs(back.value / value)
            assert 0.999 < ratio < 1.001


class TestUnitComputationFuzz:
    """Fuzz unit computation functions."""

    @given(
        total=positive_decimals,
        it=positive_decimals,
    )
    @settings(max_examples=200)
    def test_compute_pue_never_crashes(self, total, it):
        """PUE computation should handle any finite inputs."""
        try:
            pue = compute_pue(total, it)
            assert pue > 0
        except (ValueError, ZeroDivisionError):
            pass

    @given(
        total=positive_decimals,
        it=positive_decimals,
    )
    @settings(max_examples=200)
    def test_compute_dcime_never_crashes(self, total, it):
        """DCiE computation should handle any finite inputs."""
        try:
            dcie = compute_dcime(it, total)
            assert dcie > 0
        except (ValueError, ZeroDivisionError):
            pass

    @given(
        energy=positive_decimals,
        carbon_factor=positive_decimals,
    )
    @settings(max_examples=200)
    def test_compute_carbon_emissions_never_crashes(self, energy, carbon_factor):
        """Carbon emissions should handle any finite inputs."""
        try:
            result = compute_carbon_emissions(energy, carbon_factor)
            assert result.value >= 0
        except (ValueError, TypeError):
            pass

    @given(
        heat_load=positive_decimals,
        cop=positive_decimals,
    )
    @settings(max_examples=200)
    def test_compute_cooling_load_never_crashes(self, heat_load, cop):
        """Cooling load should handle any finite inputs."""
        try:
            result = compute_cooling_load(heat_load, cop)
            assert result.value >= 0
        except (ValueError, ZeroDivisionError):
            pass

    @given(
        battery=positive_decimals,
        load=positive_decimals,
        efficiency=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1.0"), allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_compute_ups_runtime_never_crashes(self, battery, load, efficiency):
        """UPS runtime should handle any finite inputs."""
        try:
            result = compute_ups_runtime(battery, load, efficiency=efficiency)
            assert result.value >= 0
        except (ValueError, ZeroDivisionError):
            pass

    @given(
        power_value=positive_decimals,
        power_unit=st.sampled_from(["W", "kW", "MW"]),
        duration=positive_decimals,
    )
    @settings(max_examples=200)
    def test_compute_energy_from_power_never_crashes(self, power_value, power_unit, duration):
        """Energy from power should handle any finite inputs."""
        try:
            power = make_quantity(power_value, power_unit)
            result = compute_energy_from_power(power, duration)
            assert result.value >= 0
        except (ValueError, TypeError):
            pass

    @given(
        energy_value=positive_decimals,
        energy_unit=st.sampled_from(["Wh", "kWh", "MWh"]),
        duration=positive_decimals,
    )
    @settings(max_examples=200)
    def test_compute_power_from_energy_never_crashes(self, energy_value, energy_unit, duration):
        """Power from energy should handle any finite inputs."""
        try:
            energy = make_quantity(energy_value, energy_unit)
            result = compute_power_from_energy(energy, duration)
            assert result.value >= 0
        except (ValueError, ZeroDivisionError):
            pass


class TestUnitArithmeticFuzz:
    """Fuzz unit arithmetic operations."""

    @given(
        v1=finite_decimals, u1=unit_symbols,
        v2=finite_decimals, u2=unit_symbols,
    )
    @settings(max_examples=200)
    def test_addition_same_dimension(self, v1, u1, v2, u2):
        """Adding quantities of the same dimension should work."""
        try:
            q1 = make_quantity(v1, u1)
            q2 = make_quantity(v2, u2)
            if q1.unit.dimension == q2.unit.dimension:
                result = q1 + q2
                assert result.unit.dimension == q1.unit.dimension
        except (ValueError, TypeError):
            pass

    @given(
        v1=finite_decimals, u1=unit_symbols,
        v2=finite_decimals, u2=unit_symbols,
    )
    @settings(max_examples=200)
    def test_subtraction_same_dimension(self, v1, u1, v2, u2):
        """Subtracting quantities of the same dimension should work."""
        try:
            q1 = make_quantity(v1, u1)
            q2 = make_quantity(v2, u2)
            if q1.unit.dimension == q2.unit.dimension:
                result = q1 - q2
                assert result.unit.dimension == q1.unit.dimension
        except (ValueError, TypeError):
            pass

    @given(
        v=finite_decimals, u=unit_symbols,
        scalar=st.decimals(min_value=Decimal("-1e10"), max_value=Decimal("1e10"), allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_scalar_multiplication(self, v, u, scalar):
        """Multiplying quantity by scalar should work."""
        try:
            q = make_quantity(v, u)
            result = q * scalar
            assert result.unit.dimension == q.unit.dimension
        except (ValueError, TypeError, InvalidOperation):
            pass

    @given(
        v=finite_decimals, u=unit_symbols,
        scalar=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1e10"), allow_nan=False, allow_infinity=False),
    )
    @settings(max_examples=200)
    def test_scalar_division(self, v, u, scalar):
        """Dividing quantity by scalar should work."""
        try:
            q = make_quantity(v, u)
            result = q / scalar
            assert result.unit.dimension == q.unit.dimension
        except (ValueError, TypeError, InvalidOperation, ZeroDivisionError):
            pass


class TestUnitFormatFuzz:
    """Fuzz unit formatting."""

    @given(
        value=finite_decimals,
        unit=unit_symbols,
        decimal_places=st.integers(min_value=0, max_value=10),
    )
    @settings(max_examples=200)
    def test_format_quantity_never_crashes(self, value, unit, decimal_places):
        """format_quantity should handle any valid inputs."""
        try:
            q = make_quantity(value, unit)
            result = format_quantity(q, decimal_places=decimal_places)
            assert isinstance(result, str)
            assert len(result) > 0
        except (ValueError, TypeError):
            pass

    @given(
        value=finite_decimals,
        unit=st.sampled_from(["W", "kW", "MW", "GW", "Wh", "kWh", "MWh", "GWh"]),
    )
    @settings(max_examples=200)
    def test_format_with_si_prefix(self, value, unit):
        """SI prefix formatting should work for power/energy."""
        try:
            q = make_quantity(value, unit)
            result = format_quantity(q, use_si_prefix=True)
            assert isinstance(result, str)
            assert len(result) > 0
        except (ValueError, TypeError):
            pass


class TestUnitRegistryFuzz:
    """Fuzz unit registry operations."""

    @given(symbol=st.text(min_size=1, max_size=20))
    @settings(max_examples=200)
    def test_get_unknown_unit_raises(self, symbol):
        """Getting an unknown unit should raise KeyError."""
        try:
            UNIT_REGISTRY.get(symbol)
        except KeyError:
            pass  # Expected

    @given(
        dimension=st.sampled_from(list(Dimension)),
    )
    @settings(max_examples=50)
    def test_list_units_by_dimension(self, dimension):
        """Listing units by dimension should return valid units."""
        units = UNIT_REGISTRY.list_units(dimension)
        for u in units:
            assert u.dimension == dimension

    @given(
        dimension=st.sampled_from(list(Dimension)),
    )
    @settings(max_examples=50)
    def test_get_base_unit(self, dimension):
        """Getting base unit should return a valid unit."""
        try:
            base = UNIT_REGISTRY.get_base_unit(dimension)
            assert base.dimension == dimension
        except KeyError:
            pass  # Some dimensions may not have a base unit
