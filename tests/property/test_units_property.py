"""Property-based tests for unit conversion system.

Tests invariants that should hold for all valid inputs:
- Round-trip conversions preserve value (within precision)
- Conversion is transitive: A->B->C == A->C
- Addition is commutative for same-dimension quantities
- Multiplication by scalar is associative
- Temperature conversions satisfy known physical constraints
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from dcc.validation.units import (
    Dimension,
    Quantity,
    UNIT_REGISTRY,
    Unit,
    compute_cooling_load,
    compute_dcime,
    compute_energy_from_power,
    compute_pue,
    compute_power_from_energy,
    compute_ups_runtime,
    convert,
    convert_temperature,
    convert_with_power_factor,
    format_quantity,
    make_quantity,
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

finite_decimals = st.decimals(
    min_value=-1e15,
    max_value=1e15,
    allow_nan=False,
    allow_infinity=False,
    places=6,
)

positive_decimals = st.decimals(
    min_value=Decimal("0.001"),
    max_value=Decimal("1e12"),
    allow_nan=False,
    allow_infinity=False,
    places=6,
)

power_units = st.sampled_from(["W", "kW", "MW", "GW", "VA", "kVA", "MVA"])
energy_units = st.sampled_from(["Wh", "kWh", "MWh", "GWh", "J", "kJ", "MJ", "BTU"])
temperature_units = st.sampled_from(["K", "°C", "°F", "°R"])
pressure_units = st.sampled_from(["Pa", "kPa", "bar", "psi", "atm"])
flow_units = st.sampled_from(["m³/s", "m³/h", "L/min", "GPM", "CFM"])
length_units = st.sampled_from(["m", "km", "cm", "mm", "ft", "in"])
mass_units = st.sampled_from(["kg", "g", "t", "lb", "oz"])
time_units = st.sampled_from(["s", "min", "h", "d", "wk"])
data_units = st.sampled_from(["B", "kB", "MB", "GB", "TB", "KiB", "MiB", "GiB"])


# ---------------------------------------------------------------------------
# Round-trip conversion property
# ---------------------------------------------------------------------------


@given(value=finite_decimals, unit_symbol=power_units)
@settings(max_examples=200)
def test_power_round_trip_through_base(value, unit_symbol):
    """Converting a power quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    # Allow for sig-fig rounding
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


@given(value=finite_decimals, unit_symbol=energy_units)
@settings(max_examples=200)
def test_energy_round_trip_through_base(value, unit_symbol):
    """Converting an energy quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


@given(value=finite_decimals, unit_symbol=pressure_units)
@settings(max_examples=200)
def test_pressure_round_trip_through_base(value, unit_symbol):
    """Converting a pressure quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


@given(value=finite_decimals, unit_symbol=length_units)
@settings(max_examples=200)
def test_length_round_trip_through_base(value, unit_symbol):
    """Converting a length quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


@given(value=finite_decimals, unit_symbol=mass_units)
@settings(max_examples=200)
def test_mass_round_trip_through_base(value, unit_symbol):
    """Converting a mass quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


@given(value=finite_decimals, unit_symbol=time_units)
@settings(max_examples=200)
def test_time_round_trip_through_base(value, unit_symbol):
    """Converting a time quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


@given(value=finite_decimals, unit_symbol=data_units)
@settings(max_examples=200)
def test_data_round_trip_through_base(value, unit_symbol):
    """Converting a data quantity to base and back preserves the value."""
    q = make_quantity(value, unit_symbol)
    base = q.to_base()
    back = base.to(unit_symbol)
    if q.value != 0:
        rel_error = abs(back.value - q.value) / abs(q.value)
        assert rel_error < Decimal("0.01"), f"Round-trip error too large: {rel_error}"


# ---------------------------------------------------------------------------
# Transitivity property: A->B->C == A->C
# ---------------------------------------------------------------------------


@given(
    value=finite_decimals,
    unit_a=power_units,
    unit_b=power_units,
    unit_c=power_units,
)
@settings(max_examples=150)
def test_power_conversion_transitive(value, unit_a, unit_b, unit_c):
    """Converting A->B->C should equal A->C (within precision)."""
    q = make_quantity(value, unit_a)
    direct = q.to(unit_c)
    indirect = q.to(unit_b).to(unit_c)
    if value != 0:
        rel_error = abs(direct.value - indirect.value) / max(abs(direct.value), Decimal("1e-30"))
        assert rel_error < Decimal("0.01"), (
            f"Transitive error: direct={direct.value}, indirect={indirect.value}"
        )


@given(
    value=finite_decimals,
    unit_a=energy_units,
    unit_b=energy_units,
    unit_c=energy_units,
)
@settings(max_examples=150)
def test_energy_conversion_transitive(value, unit_a, unit_b, unit_c):
    """Converting A->B->C should equal A->C (within precision)."""
    q = make_quantity(value, unit_a)
    direct = q.to(unit_c)
    indirect = q.to(unit_b).to(unit_c)
    if value != 0:
        rel_error = abs(direct.value - indirect.value) / max(abs(direct.value), Decimal("1e-30"))
        assert rel_error < Decimal("0.01"), (
            f"Transitive error: direct={direct.value}, indirect={indirect.value}"
        )


# ---------------------------------------------------------------------------
# Temperature-specific properties
# ---------------------------------------------------------------------------


@given(celsius=st.decimals(min_value=Decimal("-273.15"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False, places=4))
@settings(max_examples=200)
def test_celsius_fahrenheit_round_trip(celsius):
    """C->F->C should preserve the temperature."""
    f = convert_temperature(celsius, "C", "F")
    c_back = convert_temperature(f.value, "F", "C")
    assert abs(c_back.value - celsius) < Decimal("0.01"), (
        f"C->F->C round trip failed: {celsius} -> {f.value} -> {c_back.value}"
    )


@given(celsius=st.decimals(min_value=Decimal("-273.15"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False, places=4))
@settings(max_examples=200)
def test_celsius_kelvin_round_trip(celsius):
    """C->K->C should preserve the temperature."""
    k = convert_temperature(celsius, "C", "K")
    c_back = convert_temperature(k.value, "K", "C")
    assert abs(c_back.value - celsius) < Decimal("0.01"), (
        f"C->K->C round trip failed: {celsius} -> {k.value} -> {c_back.value}"
    )


@given(celsius=st.decimals(min_value=Decimal("-273.15"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False, places=4))
@settings(max_examples=200)
def test_kelvin_always_non_negative(celsius):
    """Kelvin temperature should always be >= 0 for valid Celsius inputs."""
    k = convert_temperature(celsius, "C", "K")
    assert k.value >= 0, f"Kelvin should be >= 0, got {k.value} for {celsius}°C"


@given(
    celsius=st.decimals(min_value=Decimal("-273.15"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False, places=4)
)
@settings(max_examples=200)
def test_fahrenheit_freezing_boiling_points(celsius):
    """Water freezes at 32°F and boils at 212°F at standard pressure."""
    freezing = convert_temperature(Decimal("0"), "C", "F")
    boiling = convert_temperature(Decimal("100"), "C", "F")
    assert abs(freezing.value - Decimal("32")) < Decimal("0.1")
    assert abs(boiling.value - Decimal("212")) < Decimal("0.1")


# ---------------------------------------------------------------------------
# Arithmetic properties
# ---------------------------------------------------------------------------


@given(a=finite_decimals, b=finite_decimals, unit_symbol=power_units)
@settings(max_examples=200)
def test_addition_commutative_same_unit(a, b, unit_symbol):
    """a + b == b + a for quantities in the same unit."""
    qa = make_quantity(a, unit_symbol)
    qb = make_quantity(b, unit_symbol)
    assert qa + qb == qb + qa


@given(a=finite_decimals, b=finite_decimals, unit_symbol=energy_units)
@settings(max_examples=200)
def test_addition_commutative_energy(a, b, unit_symbol):
    """a + b == b + a for energy quantities."""
    qa = make_quantity(a, unit_symbol)
    qb = make_quantity(b, unit_symbol)
    assert qa + qb == qb + qa


@given(a=finite_decimals, b=finite_decimals, c=finite_decimals, unit_symbol=power_units)
@settings(max_examples=150)
def test_addition_associative(a, b, c, unit_symbol):
    """(a + b) + c == a + (b + c) for quantities."""
    qa = make_quantity(a, unit_symbol)
    qb = make_quantity(b, unit_symbol)
    qc = make_quantity(c, unit_symbol)
    left = (qa + qb) + qc
    right = qa + (qb + qc)
    assert left == right


@given(value=finite_decimals, scalar=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False, places=4), unit_symbol=power_units)
@settings(max_examples=200)
def test_scalar_multiplication_preserves_dimension(value, scalar, unit_symbol):
    """Multiplying a quantity by a scalar preserves its dimension."""
    q = make_quantity(value, unit_symbol)
    result = q * scalar
    assert result.unit.dimension == q.unit.dimension
    assert result.unit.symbol == q.unit.symbol


@given(value=finite_decimals, scalar=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("1000"), allow_nan=False, allow_infinity=False, places=4), unit_symbol=energy_units)
@settings(max_examples=200)
def test_scalar_multiplication_linear(value, scalar, unit_symbol):
    """(q * s1) * s2 == q * (s1 * s2) for scalar multiplication."""
    s2 = Decimal("2.5")
    q = make_quantity(value, unit_symbol)
    left = (q * scalar) * s2
    right = q * (scalar * s2)
    if value != 0:
        rel_error = abs(left.value - right.value) / max(abs(left.value), Decimal("1e-30"))
        assert rel_error < Decimal("0.01")


# ---------------------------------------------------------------------------
# Cross-dimension conversion should fail
# ---------------------------------------------------------------------------


@given(value=finite_decimals)
@settings(max_examples=100)
def test_cross_dimension_conversion_raises(value):
    """Converting between different dimensions should raise ValueError."""
    q = make_quantity(value, "kW")
    with pytest.raises(ValueError, match="Cannot convert"):
        q.to("kWh")


@given(value=finite_decimals)
@settings(max_examples=100)
def test_incompatible_addition_raises(value):
    """Adding quantities of different dimensions should raise ValueError."""
    q_power = make_quantity(value, "kW")
    q_energy = make_quantity(value, "kWh")
    with pytest.raises(ValueError, match="Cannot add"):
        q_power + q_energy


# ---------------------------------------------------------------------------
# PUE and DCiE properties
# ---------------------------------------------------------------------------


@given(
    total=positive_decimals,
    it=positive_decimals,
)
@settings(max_examples=200)
def test_pue_dcime_reciprocal(total, it):
    """PUE * DCiE should equal 1 when both are computed from the same inputs."""
    pue = compute_pue(total, it)
    dcie = compute_dcime(it, total)
    product = pue * dcie
    assert abs(product - Decimal("1")) < Decimal("0.0001"), (
        f"PUE * DCiE = {product}, expected 1"
    )


@given(
    total=positive_decimals,
    it=positive_decimals,
)
@settings(max_examples=200)
def test_pue_always_gte_one(total, it):
    """PUE should always be >= 1 when total >= it (facility includes IT)."""
    if total >= it:
        pue = compute_pue(total, it)
        assert pue >= Decimal("1"), f"PUE {pue} < 1 for total={total}, it={it}"


# ---------------------------------------------------------------------------
# Energy-power relationship properties
# ---------------------------------------------------------------------------


@given(
    power=positive_decimals,
    hours=st.decimals(min_value=Decimal("0.001"), max_value=Decimal("8760"), allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=200)
def test_energy_power_round_trip(power, hours):
    """Energy = Power * hours, then Power = Energy / hours should round-trip."""
    p = make_quantity(power, "kW")
    energy = compute_energy_from_power(p, hours, sig_figs=None)
    power_back = compute_power_from_energy(energy, hours, sig_figs=None)
    if power != 0:
        rel_error = abs(power_back.value - power) / power
        assert rel_error < Decimal("0.01"), (
            f"Power round-trip failed: {power} -> {energy.value} kWh -> {power_back.value}"
        )


# ---------------------------------------------------------------------------
# Power factor conversion properties
# ---------------------------------------------------------------------------


@given(
    value=positive_decimals,
    pf=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1"), allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=200)
def test_va_w_conversion_with_power_factor(value, pf):
    """VA * PF = W, and W / PF = VA."""
    w = convert_with_power_factor(value, "VA", "W", pf)
    va_back = convert_with_power_factor(w.value, "W", "VA", pf)
    if value != 0:
        rel_error = abs(va_back.value - value) / value
        assert rel_error < Decimal("0.01"), (
            f"VA->W->VA round trip failed: {value} -> {w.value} -> {va_back.value}"
        )


@given(
    value=positive_decimals,
    pf=st.decimals(min_value=Decimal("0.01"), max_value=Decimal("1"), allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=200)
def test_w_always_lte_va(value, pf):
    """Real power (W) should always be <= apparent power (VA) for PF <= 1."""
    w = convert_with_power_factor(value, "VA", "W", pf)
    assert w.value <= value, f"W ({w.value}) > VA ({value}) for PF={pf}"


# ---------------------------------------------------------------------------
# Cooling load properties
# ---------------------------------------------------------------------------


@given(
    heat_load=positive_decimals,
    cop=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("20"), allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=200)
def test_cooling_load_positive(heat_load, cop):
    """Cooling load should always be positive for positive heat load and COP."""
    cooling = compute_cooling_load(heat_load, cop)
    assert cooling.value > 0, f"Cooling load {cooling.value} <= 0"


@given(
    heat_load=positive_decimals,
    cop=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("20"), allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=200)
def test_cooling_load_scales_with_cop(heat_load, cop):
    """Higher COP means lower cooling load for the same heat load."""
    cooling1 = compute_cooling_load(heat_load, cop)
    cooling2 = compute_cooling_load(heat_load, cop * Decimal("2"))
    assert cooling2.value < cooling1.value, (
        f"Higher COP should mean lower cooling: {cooling2.value} >= {cooling1.value}"
    )


# ---------------------------------------------------------------------------
# UPS runtime properties
# ---------------------------------------------------------------------------


@given(
    capacity=positive_decimals,
    load=positive_decimals,
    efficiency=st.decimals(min_value=Decimal("0.1"), max_value=Decimal("1"), allow_nan=False, allow_infinity=False, places=4),
)
@settings(max_examples=200)
def test_ups_runtime_positive(capacity, load, efficiency):
    """UPS runtime should always be positive for positive capacity and load."""
    runtime = compute_ups_runtime(capacity, load, efficiency=efficiency)
    assert runtime.value > 0, f"UPS runtime {runtime.value} <= 0"


@given(
    capacity=positive_decimals,
    load=positive_decimals,
)
@settings(max_examples=200)
def test_ups_runtime_scales_with_capacity(capacity, load):
    """Doubling battery capacity should double the runtime."""
    runtime1 = compute_ups_runtime(capacity, load, sig_figs=None)
    runtime2 = compute_ups_runtime(capacity * Decimal("2"), load, sig_figs=None)
    ratio = runtime2.value / runtime1.value
    assert abs(ratio - Decimal("2")) < Decimal("0.01"), (
        f"Runtime ratio {ratio} != 2 when capacity doubled"
    )


# ---------------------------------------------------------------------------
# Format properties
# ---------------------------------------------------------------------------


@given(value=finite_decimals, unit_symbol=power_units)
@settings(max_examples=100)
def test_format_quantity_contains_unit_symbol(value, unit_symbol):
    """Formatted quantity should contain the unit symbol."""
    q = make_quantity(value, unit_symbol)
    formatted = format_quantity(q)
    assert unit_symbol in formatted, f"Unit symbol '{unit_symbol}' not in '{formatted}'"


@given(value=finite_decimals, unit_symbol=energy_units)
@settings(max_examples=100)
def test_format_quantity_contains_value(value, unit_symbol):
    """Formatted quantity should contain the numeric value."""
    q = make_quantity(value, unit_symbol)
    formatted = format_quantity(q)
    # The value should appear in the formatted string
    assert str(value) in formatted or str(int(value)) in formatted, (
        f"Value {value} not found in '{formatted}'"
    )


# ---------------------------------------------------------------------------
# Registry properties
# ---------------------------------------------------------------------------


def test_all_power_units_share_dimension():
    """All power units should have the POWER dimension."""
    for sym in ["W", "kW", "MW", "GW", "VA", "kVA", "MVA", "BTU/h", "RT", "hp"]:
        unit = UNIT_REGISTRY.get(sym)
        assert unit.dimension == Dimension.POWER, f"{sym} has dimension {unit.dimension}"


def test_all_energy_units_share_dimension():
    """All energy units should have the ENERGY dimension."""
    for sym in ["Wh", "kWh", "MWh", "GWh", "J", "kJ", "MJ", "GJ", "BTU", "kBTU", "thm", "cal", "kcal"]:
        unit = UNIT_REGISTRY.get(sym)
        assert unit.dimension == Dimension.ENERGY, f"{sym} has dimension {unit.dimension}"


def test_all_temperature_units_share_dimension():
    """All temperature units should have the TEMPERATURE dimension."""
    for sym in ["K", "°C", "°F", "°R"]:
        unit = UNIT_REGISTRY.get(sym)
        assert unit.dimension == Dimension.TEMPERATURE, f"{sym} has dimension {unit.dimension}"


@given(unit_symbol=st.sampled_from(["W", "kW", "MW", "GW", "VA", "kVA", "MVA", "BTU/h", "RT", "hp"]))
@settings(max_examples=50)
def test_power_unit_to_base_positive(unit_symbol):
    """All power units should have positive to_base conversion factor."""
    unit = UNIT_REGISTRY.get(unit_symbol)
    assert unit.to_base > 0, f"{unit_symbol} has non-positive to_base: {unit.to_base}"


@given(unit_symbol=st.sampled_from(["Wh", "kWh", "MWh", "GWh", "J", "kJ", "MJ", "GJ", "BTU", "kBTU", "thm", "cal", "kcal"]))
@settings(max_examples=50)
def test_energy_unit_to_base_positive(unit_symbol):
    """All energy units should have positive to_base conversion factor."""
    unit = UNIT_REGISTRY.get(unit_symbol)
    assert unit.to_base > 0, f"{unit_symbol} has non-positive to_base: {unit.to_base}"
