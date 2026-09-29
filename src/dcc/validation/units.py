"""Unit conversion system with precision tracking for Data Center Commander.

Supports data-center domain conversions: power (W, kW, MW, VA),
energy (Wh, kWh, MWh), temperature (°C, °F, K), pressure (Pa, bar, psi),
flow (L/min, m³/h, CFM), and more.

All conversions use Decimal arithmetic and track significant figures.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP, getcontext
from enum import Enum

getcontext().prec = 50


class Dimension(Enum):
    """Physical dimension categories."""

    POWER = "power"
    ENERGY = "energy"
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    FLOW = "flow"
    LENGTH = "length"
    AREA = "area"
    VOLUME = "volume"
    MASS = "mass"
    TIME = "time"
    FREQUENCY = "frequency"
    CURRENT = "current"
    VOLTAGE = "voltage"
    POWER_FACTOR = "power_factor"
    EFFICIENCY = "efficiency"
    CARBON_INTENSITY = "carbon_intensity"
    DATA = "data"
    CURRENCY = "currency"


@dataclass(frozen=True)
class Unit:
    """A unit definition with conversion metadata."""

    name: str
    symbol: str
    dimension: Dimension
    to_base: Decimal = Decimal(1)
    offset: Decimal = Decimal(0)
    base_unit: str | None = None

    def __post_init__(self):
        if self.to_base == 0:
            raise ValueError(f"Unit {self.name}: to_base cannot be zero")


@dataclass
class Quantity:
    """A measured value with unit and precision metadata."""

    value: Decimal
    unit: Unit
    sig_figs: int | None = None

    def __post_init__(self):
        if self.sig_figs is not None and self.sig_figs < 1:
            raise ValueError("sig_figs must be >= 1 or None")
        if self.value == 0:
            object.__setattr__(self, "value", Decimal(0))

    def __repr__(self) -> str:
        sig = f", sig_figs={self.sig_figs}" if self.sig_figs else ""
        return f"Quantity({self.value}, {self.unit.symbol!r}{sig})"

    def __str__(self) -> str:
        sig = f" ({self.sig_figs} sig figs)" if self.sig_figs else ""
        return f"{self.value} {self.unit.symbol}{sig}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Quantity):
            return NotImplemented
        return self.value == other.value and self.unit is other.unit

    def __hash__(self) -> int:
        return hash((self.value, self.unit.symbol, self.unit.dimension))

    def __add__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        if self.unit.dimension != other.unit.dimension:
            raise ValueError(
                f"Cannot add {self.unit.dimension.value} and {other.unit.dimension.value}"
            )
        other_converted = convert(other, self.unit)
        result = self.value + other_converted.value
        dp1 = -self.value.as_tuple().exponent if self.value.as_tuple().exponent < 0 else 0
        dp2 = -other_converted.value.as_tuple().exponent if other_converted.value.as_tuple().exponent < 0 else 0
        result_dp = max(dp1, dp2)
        if result_dp > 0:
            try:
                result = result.quantize(Decimal(1).scaleb(-result_dp), rounding=ROUND_HALF_UP)
            except Exception:
                pass  # Keep unquantized result for extreme values
        return Quantity(result, self.unit, sig_figs=None)

    def __sub__(self, other: Quantity) -> Quantity:
        if not isinstance(other, Quantity):
            return NotImplemented
        if self.unit.dimension != other.unit.dimension:
            raise ValueError(
                f"Cannot subtract {other.unit.dimension.value} from {self.unit.dimension.value}"
            )
        other_converted = convert(other, self.unit)
        result = self.value - other_converted.value
        dp1 = -self.value.as_tuple().exponent if self.value.as_tuple().exponent < 0 else 0
        dp2 = -other_converted.value.as_tuple().exponent if other_converted.value.as_tuple().exponent < 0 else 0
        result_dp = max(dp1, dp2)
        if result_dp > 0:
            try:
                result = result.quantize(Decimal(1).scaleb(-result_dp), rounding=ROUND_HALF_UP)
            except Exception:
                pass  # Keep unquantized result for extreme values
        return Quantity(result, self.unit, sig_figs=None)

    def __mul__(self, other: Decimal | int | float) -> Quantity:
        if isinstance(other, (int, float)):
            other = Decimal(str(other))
        if not isinstance(other, Decimal):
            return NotImplemented
        result = self.value * other
        other_sig = _count_sig_figs(other)
        if self.sig_figs is not None and other_sig is not None:
            sig = min(self.sig_figs, other_sig)
        elif self.sig_figs is not None:
            sig = self.sig_figs
        elif other_sig is not None:
            sig = other_sig
        else:
            sig = None
        return Quantity(result, self.unit, sig_figs=sig)

    def __rmul__(self, other: Decimal | int | float) -> Quantity:
        return self.__mul__(other)

    def __truediv__(self, other: Decimal | int | float) -> Quantity:
        if isinstance(other, (int, float)):
            other = Decimal(str(other))
        if not isinstance(other, Decimal):
            return NotImplemented
        if other == 0:
            raise ZeroDivisionError("Cannot divide quantity by zero")
        result = self.value / other
        other_sig = _count_sig_figs(other)
        if self.sig_figs is not None and other_sig is not None:
            sig = min(self.sig_figs, other_sig)
        elif self.sig_figs is not None:
            sig = self.sig_figs
        elif other_sig is not None:
            sig = other_sig
        else:
            sig = None
        return Quantity(result, self.unit, sig_figs=sig)

    def to(self, target_unit: Unit | str) -> Quantity:
        """Convert this quantity to another unit of the same dimension."""
        return convert(self, target_unit)

    def to_base(self) -> Quantity:
        """Convert to the base unit of this dimension."""
        base = UNIT_REGISTRY.get_base_unit(self.unit.dimension)
        return self.to(base)


def _count_sig_figs(d: Decimal) -> int | None:
    """Count significant figures in a Decimal value."""
    if d == 0:
        return None
    sign, digits, exponent = d.as_tuple()
    digits_list = list(digits)
    while digits_list and digits_list[0] == 0:
        digits_list.pop(0)
    if exponent >= 0:
        while digits_list and digits_list[-1] == 0:
            digits_list.pop()
    return len(digits_list) if digits_list else None


def _apply_sig_figs(value: Decimal, sig_figs: int) -> Decimal:
    """Round a Decimal to the given number of significant figures."""
    if value == 0:
        return value
    sign, digits, exponent = value.as_tuple()
    num_digits = len(digits)
    if num_digits <= sig_figs:
        return value
    round_exponent = exponent + (num_digits - sig_figs)
    quantum = Decimal(1).scaleb(round_exponent)
    return value.quantize(quantum, rounding=ROUND_HALF_UP)


class UnitRegistry:
    """Central registry of all supported units."""

    def __init__(self) -> None:
        self._units: dict[str, Unit] = {}
        self._by_dimension: dict[Dimension, list[Unit]] = {}
        self._base_units: dict[Dimension, str] = {}
        self._aliases: dict[str, str] = {}
        self._register_defaults()

    def register(self, unit: Unit, aliases: list[str] | None = None) -> None:
        """Register a unit with optional aliases."""
        key = unit.symbol.lower()
        self._units[key] = unit
        self._units[unit.name.lower()] = unit
        if aliases:
            for alias in aliases:
                self._aliases[alias.lower()] = key
        if unit.dimension not in self._by_dimension:
            self._by_dimension[unit.dimension] = []
        self._by_dimension[unit.dimension].append(unit)
        if unit.base_unit:
            self._base_units[unit.dimension] = unit.base_unit

    def get(self, symbol_or_name: str) -> Unit:
        """Look up a unit by symbol or name."""
        key = symbol_or_name.lower()
        if key in self._aliases:
            key = self._aliases[key]
        if key in self._units:
            return self._units[key]
        raise KeyError(f"Unknown unit: {symbol_or_name!r}")

    def get_base_unit(self, dimension: Dimension) -> Unit:
        """Get the base unit for a dimension."""
        base_name = self._base_units.get(dimension)
        if base_name is None:
            raise KeyError(f"No base unit defined for {dimension.value}")
        return self.get(base_name)

    def list_units(self, dimension: Dimension | None = None) -> list[Unit]:
        """List all registered units, optionally filtered by dimension."""
        if dimension is None:
            return list(self._units.values())
        return self._by_dimension.get(dimension, [])

    def _register_defaults(self) -> None:
        """Register all default data-center units."""

        # === POWER (base: W) ===
        self.register(Unit("watt", "W", Dimension.POWER, Decimal(1), base_unit="W"))
        self.register(Unit("kilowatt", "kW", Dimension.POWER, Decimal(1000)))
        self.register(Unit("megawatt", "MW", Dimension.POWER, Decimal(1_000_000)))
        self.register(Unit("gigawatt", "GW", Dimension.POWER, Decimal(1_000_000_000)))
        self.register(Unit("volt-ampere", "VA", Dimension.POWER, Decimal(1)))
        self.register(Unit("kilovolt-ampere", "kVA", Dimension.POWER, Decimal(1000)))
        self.register(Unit("megavolt-ampere", "MVA", Dimension.POWER, Decimal(1_000_000)))
        self.register(Unit("British thermal unit per hour", "BTU/h", Dimension.POWER, Decimal("0.29307107")))
        self.register(Unit("refrigeration ton", "RT", Dimension.POWER, Decimal("3516.85284")))
        self.register(Unit("horsepower", "hp", Dimension.POWER, Decimal("745.699872")))

        # === ENERGY (base: Wh) ===
        self.register(Unit("watt-hour", "Wh", Dimension.ENERGY, Decimal(1), base_unit="Wh"))
        self.register(Unit("kilowatt-hour", "kWh", Dimension.ENERGY, Decimal(1000)))
        self.register(Unit("megawatt-hour", "MWh", Dimension.ENERGY, Decimal(1_000_000)))
        self.register(Unit("gigawatt-hour", "GWh", Dimension.ENERGY, Decimal(1_000_000_000)))
        self.register(Unit("joule", "J", Dimension.ENERGY, Decimal("0.000277777778")))
        self.register(Unit("kilojoule", "kJ", Dimension.ENERGY, Decimal("0.277777778")))
        self.register(Unit("megajoule", "MJ", Dimension.ENERGY, Decimal("277.777778")))
        self.register(Unit("gigajoule", "GJ", Dimension.ENERGY, Decimal("277777.778")))
        self.register(Unit("British thermal unit", "BTU", Dimension.ENERGY, Decimal("0.29307107")))
        self.register(Unit("kilobritish thermal unit", "kBTU", Dimension.ENERGY, Decimal("293.07107")))
        self.register(Unit("therm", "thm", Dimension.ENERGY, Decimal("29307.107")))
        self.register(Unit("calorie", "cal", Dimension.ENERGY, Decimal("0.00116222222")))
        self.register(Unit("kilocalorie", "kcal", Dimension.ENERGY, Decimal("1.16222222")))

        # === TEMPERATURE (base: K) ===
        self.register(Unit("kelvin", "K", Dimension.TEMPERATURE, Decimal(1), base_unit="K"))
        self.register(Unit("degree Celsius", "°C", Dimension.TEMPERATURE, Decimal(1), Decimal(273.15)))
        self.register(Unit("degree Fahrenheit", "°F", Dimension.TEMPERATURE, Decimal("5") / Decimal("9"), Decimal("459.67") * Decimal("5") / Decimal("9")))
        self.register(Unit("degree Rankine", "°R", Dimension.TEMPERATURE, Decimal("5") / Decimal("9")))

        # === PRESSURE (base: Pa) ===
        self.register(Unit("pascal", "Pa", Dimension.PRESSURE, Decimal(1), base_unit="Pa"))
        self.register(Unit("kilopascal", "kPa", Dimension.PRESSURE, Decimal(1000)))
        self.register(Unit("megapascal", "MPa", Dimension.PRESSURE, Decimal(1_000_000)))
        self.register(Unit("bar", "bar", Dimension.PRESSURE, Decimal(100_000)))
        self.register(Unit("millibar", "mbar", Dimension.PRESSURE, Decimal(100)))
        self.register(Unit("pounds per square inch", "psi", Dimension.PRESSURE, Decimal("6894.757293168")))
        self.register(Unit("inches of water", "inH2O", Dimension.PRESSURE, Decimal("249.088908333")))
        self.register(Unit("inches of mercury", "inHg", Dimension.PRESSURE, Decimal("3386.389")))
        self.register(Unit("atmosphere", "atm", Dimension.PRESSURE, Decimal("101325")))

        # === FLOW (base: m³/s) ===
        self.register(Unit("cubic meter per second", "m³/s", Dimension.FLOW, Decimal(1), base_unit="m³/s"))
        self.register(Unit("cubic meter per hour", "m³/h", Dimension.FLOW, Decimal(1) / Decimal(3600)))
        self.register(Unit("cubic meter per minute", "m³/min", Dimension.FLOW, Decimal(1) / Decimal(60)))
        self.register(Unit("liter per second", "L/s", Dimension.FLOW, Decimal("0.001")))
        self.register(Unit("liter per minute", "L/min", Dimension.FLOW, Decimal("0.001") / Decimal(60)))
        self.register(Unit("gallon per minute", "GPM", Dimension.FLOW, Decimal("0.00378541178") / Decimal(60)))
        self.register(Unit("cubic feet per minute", "CFM", Dimension.FLOW, Decimal("0.0283168466") / Decimal(60)))
        self.register(Unit("cubic feet per second", "ft³/s", Dimension.FLOW, Decimal("0.0283168466")))

        # === LENGTH (base: m) ===
        self.register(Unit("meter", "m", Dimension.LENGTH, Decimal(1), base_unit="m"))
        self.register(Unit("kilometer", "km", Dimension.LENGTH, Decimal(1000)))
        self.register(Unit("centimeter", "cm", Dimension.LENGTH, Decimal("0.01")))
        self.register(Unit("millimeter", "mm", Dimension.LENGTH, Decimal("0.001")))
        self.register(Unit("foot", "ft", Dimension.LENGTH, Decimal("0.3048")))
        self.register(Unit("inch", "in", Dimension.LENGTH, Decimal("0.0254")))
        self.register(Unit("mile", "mi", Dimension.LENGTH, Decimal("1609.344")))
        self.register(Unit("yard", "yd", Dimension.LENGTH, Decimal("0.9144")))

        # === AREA (base: m²) ===
        self.register(Unit("square meter", "m²", Dimension.AREA, Decimal(1), base_unit="m²"))
        self.register(Unit("square foot", "ft²", Dimension.AREA, Decimal("0.09290304")))
        self.register(Unit("square kilometer", "km²", Dimension.AREA, Decimal(1_000_000)))
        self.register(Unit("acre", "ac", Dimension.AREA, Decimal("4046.8564224")))
        self.register(Unit("hectare", "ha", Dimension.AREA, Decimal(10_000)))

        # === VOLUME (base: m³) ===
        self.register(Unit("cubic meter", "m³", Dimension.VOLUME, Decimal(1), base_unit="m³"))
        self.register(Unit("liter", "L", Dimension.VOLUME, Decimal("0.001")))
        self.register(Unit("milliliter", "mL", Dimension.VOLUME, Decimal("0.000001")))
        self.register(Unit("gallon (US)", "gal", Dimension.VOLUME, Decimal("0.00378541178")))
        self.register(Unit("cubic foot", "ft³", Dimension.VOLUME, Decimal("0.0283168466")))

        # === MASS (base: kg) ===
        self.register(Unit("kilogram", "kg", Dimension.MASS, Decimal(1), base_unit="kg"))
        self.register(Unit("gram", "g", Dimension.MASS, Decimal("0.001")))
        self.register(Unit("metric ton", "t", Dimension.MASS, Decimal(1000)))
        self.register(Unit("pound", "lb", Dimension.MASS, Decimal("0.45359237")))
        self.register(Unit("ounce", "oz", Dimension.MASS, Decimal("0.0283495231")))

        # === TIME (base: s) ===
        self.register(Unit("second", "s", Dimension.TIME, Decimal(1), base_unit="s"))
        self.register(Unit("minute", "min", Dimension.TIME, Decimal(60)))
        self.register(Unit("hour", "h", Dimension.TIME, Decimal(3600)))
        self.register(Unit("day", "d", Dimension.TIME, Decimal(86400)))
        self.register(Unit("week", "wk", Dimension.TIME, Decimal(604800)))
        self.register(Unit("month (30d)", "mo", Dimension.TIME, Decimal(2_592_000)))
        self.register(Unit("year (365d)", "yr", Dimension.TIME, Decimal(31_536_000)))

        # === FREQUENCY (base: Hz) ===
        self.register(Unit("hertz", "Hz", Dimension.FREQUENCY, Decimal(1), base_unit="Hz"))
        self.register(Unit("kilohertz", "kHz", Dimension.FREQUENCY, Decimal(1000)))
        self.register(Unit("megahertz", "MHz", Dimension.FREQUENCY, Decimal(1_000_000)))
        self.register(Unit("gigahertz", "GHz", Dimension.FREQUENCY, Decimal(1_000_000_000)))

        # === CURRENT (base: A) ===
        self.register(Unit("ampere", "A", Dimension.CURRENT, Decimal(1), base_unit="A"))
        self.register(Unit("milliampere", "mA", Dimension.CURRENT, Decimal("0.001")))
        self.register(Unit("kiloampere", "kA", Dimension.CURRENT, Decimal(1000)))

        # === VOLTAGE (base: V) ===
        self.register(Unit("volt", "V", Dimension.VOLTAGE, Decimal(1), base_unit="V"))
        self.register(Unit("millivolt", "mV", Dimension.VOLTAGE, Decimal("0.001")))
        self.register(Unit("kilovolt", "kV", Dimension.VOLTAGE, Decimal(1000)))

        # === POWER FACTOR (base: ratio) ===
        self.register(Unit("power factor", "PF", Dimension.POWER_FACTOR, Decimal(1), base_unit="PF"))
        self.register(Unit("power factor percent", "PF%", Dimension.POWER_FACTOR, Decimal("0.01")))

        # === EFFICIENCY (base: ratio) ===
        self.register(Unit("efficiency ratio", "η", Dimension.EFFICIENCY, Decimal(1), base_unit="η"))
        self.register(Unit("efficiency percent", "%", Dimension.EFFICIENCY, Decimal("0.01")))
        self.register(Unit("PUE", "PUE", Dimension.EFFICIENCY, Decimal(1)))
        self.register(Unit("DCIE", "DCIE", Dimension.EFFICIENCY, Decimal(1)))

        # === CARBON INTENSITY (base: kg/kWh) ===
        self.register(Unit("kilogram per kilowatt-hour", "kg/kWh", Dimension.CARBON_INTENSITY, Decimal(1), base_unit="kg/kWh"))
        self.register(Unit("gram per kilowatt-hour", "g/kWh", Dimension.CARBON_INTENSITY, Decimal("0.001")))
        self.register(Unit("kilogram per megawatt-hour", "kg/MWh", Dimension.CARBON_INTENSITY, Decimal("0.001")))
        self.register(Unit("pound per megawatt-hour", "lb/MWh", Dimension.CARBON_INTENSITY, Decimal("0.00045359237")))

        # === DATA (base: B) ===
        self.register(Unit("byte", "B", Dimension.DATA, Decimal(1), base_unit="B"))
        self.register(Unit("kilobyte", "kB", Dimension.DATA, Decimal(1000)))
        self.register(Unit("megabyte", "MB", Dimension.DATA, Decimal(1_000_000)))
        self.register(Unit("gigabyte", "GB", Dimension.DATA, Decimal(1_000_000_000)))
        self.register(Unit("terabyte", "TB", Dimension.DATA, Decimal(1_000_000_000_000)))
        self.register(Unit("petabyte", "PB", Dimension.DATA, Decimal("1000000000000000")))
        self.register(Unit("kibibyte", "KiB", Dimension.DATA, Decimal(1024)))
        self.register(Unit("mebibyte", "MiB", Dimension.DATA, Decimal(1_048_576)))
        self.register(Unit("gibibyte", "GiB", Dimension.DATA, Decimal(1_073_741_824)))
        self.register(Unit("tebibyte", "TiB", Dimension.DATA, Decimal(1_099_511_627_776)))

        # === CURRENCY (base: USD) ===
        self.register(Unit("US dollar", "USD", Dimension.CURRENCY, Decimal(1), base_unit="USD"))
        self.register(Unit("euro", "EUR", Dimension.CURRENCY, Decimal(1)))
        self.register(Unit("British pound", "GBP", Dimension.CURRENCY, Decimal(1)))
        self.register(Unit("Japanese yen", "JPY", Dimension.CURRENCY, Decimal(1)))


UNIT_REGISTRY = UnitRegistry()


def get_registry() -> UnitRegistry:
    """Get the global unit registry."""
    return UNIT_REGISTRY


def convert(
    quantity: Quantity | Decimal | int | float,
    target_unit: Unit | str,
    *,
    source_unit: Unit | str | None = None,
) -> Quantity:
    """Convert a quantity to a target unit.

    Args:
        quantity: The value to convert (Quantity, or numeric with source_unit).
        target_unit: The target unit (Unit object or symbol string).
        source_unit: Required if quantity is not a Quantity.

    Returns:
        A new Quantity in the target unit with precision tracking.
    """
    if isinstance(target_unit, str):
        target_unit = UNIT_REGISTRY.get(target_unit)

    if isinstance(quantity, Quantity):
        source = quantity
    else:
        if source_unit is None:
            raise ValueError("source_unit is required when quantity is not a Quantity")
        if isinstance(source_unit, str):
            source_unit = UNIT_REGISTRY.get(source_unit)
        if isinstance(quantity, (int, float)):
            quantity = Decimal(str(quantity))
        source = Quantity(quantity, source_unit)

    if source.unit.dimension != target_unit.dimension:
        raise ValueError(
            f"Cannot convert {source.unit.dimension.value} to {target_unit.dimension.value}"
        )

    if source.unit.dimension == Dimension.TEMPERATURE:
        return _convert_temperature(source, target_unit)

    value_in_base = source.value * source.unit.to_base + source.unit.offset
    result_value = (value_in_base - target_unit.offset) / target_unit.to_base

    if source.sig_figs is not None:
        result_value = _apply_sig_figs(result_value, source.sig_figs)

    return Quantity(result_value, target_unit, sig_figs=source.sig_figs)


def _convert_temperature(source: Quantity, target_unit: Unit) -> Quantity:
    """Convert temperature with offset handling."""
    if source.unit.symbol == "K":
        kelvin = source.value
    elif source.unit.symbol == "°C":
        kelvin = source.value + Decimal("273.15")
    elif source.unit.symbol == "°F":
        kelvin = (source.value + Decimal("459.67")) * Decimal("5") / Decimal("9")
    elif source.unit.symbol == "°R":
        kelvin = source.value * Decimal("5") / Decimal("9")
    else:
        kelvin = source.value * source.unit.to_base + source.unit.offset

    if target_unit.symbol == "K":
        result = kelvin
    elif target_unit.symbol == "°C":
        result = kelvin - Decimal("273.15")
    elif target_unit.symbol == "°F":
        result = kelvin * Decimal("9") / Decimal("5") - Decimal("459.67")
    elif target_unit.symbol == "°R":
        result = kelvin * Decimal("9") / Decimal("5")
    else:
        result = (kelvin - target_unit.offset) / target_unit.to_base

    if source.sig_figs is not None:
        result = _apply_sig_figs(result, source.sig_figs)

    return Quantity(result, target_unit, sig_figs=source.sig_figs)


def convert_temperature(
    value: Decimal | int | float,
    from_scale: str,
    to_scale: str,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert temperature between scales.

    Args:
        value: The temperature value.
        from_scale: Source scale ("C", "F", "K", "R").
        to_scale: Target scale ("C", "F", "K", "R").
        sig_figs: Optional significant figures for precision tracking.

    Returns:
        Quantity in the target temperature scale.
    """
    if isinstance(value, (int, float)):
        value = Decimal(str(value))

    scale_map = {
        "C": "°C", "c": "°C", "celsius": "°C", "°c": "°C",
        "F": "°F", "f": "°F", "fahrenheit": "°F", "°f": "°F",
        "K": "K", "k": "K", "kelvin": "K",
        "R": "°R", "r": "°R", "rankine": "°R", "°r": "°R",
    }

    from_sym = scale_map.get(from_scale, from_scale)
    to_sym = scale_map.get(to_scale, to_scale)

    source_unit = UNIT_REGISTRY.get(from_sym)
    target_unit = UNIT_REGISTRY.get(to_sym)

    source = Quantity(value, source_unit, sig_figs=sig_figs)
    return _convert_temperature(source, target_unit)


def convert_with_power_factor(
    value: Decimal | int | float,
    from_unit: str,
    to_unit: str,
    power_factor: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert between real power (W) and apparent power (VA) using power factor.

    Args:
        value: The power value.
        from_unit: Source unit symbol.
        to_unit: Target unit symbol.
        power_factor: Power factor (0 < PF <= 1).
        sig_figs: Optional significant figures.

    Returns:
        Quantity in the target unit.

    Note:
        W = VA * PF, so VA = W / PF
    """
    if isinstance(value, (int, float)):
        value = Decimal(str(value))
    if isinstance(power_factor, (int, float)):
        power_factor = Decimal(str(power_factor))

    if power_factor <= 0 or power_factor > 1:
        raise ValueError(f"Power factor must be in (0, 1], got {power_factor}")

    source = Quantity(value, UNIT_REGISTRY.get(from_unit), sig_figs=sig_figs)
    target = UNIT_REGISTRY.get(to_unit)

    from_is_real = source.unit.symbol in ("W", "kW", "MW", "GW")
    from_is_apparent = source.unit.symbol in ("VA", "kVA", "MVA")
    to_is_real = target.symbol in ("W", "kW", "MW", "GW")
    to_is_apparent = target.symbol in ("VA", "kVA", "MVA")

    if from_is_real and to_is_apparent:
        result_value = value / power_factor
    elif from_is_apparent and to_is_real:
        result_value = value * power_factor
    elif from_is_real and to_is_real:
        result_value = value
    elif from_is_apparent and to_is_apparent:
        result_value = value
    else:
        raise ValueError(
            f"Power factor conversion only supported between W and VA families, "
            f"got {from_unit} -> {to_unit}"
        )

    if from_unit != to_unit:
        base_value = result_value * source.unit.to_base
        result_value = base_value / target.to_base

    pf_sig = _count_sig_figs(power_factor)
    if sig_figs is not None and pf_sig is not None:
        final_sig = min(sig_figs, pf_sig)
    elif sig_figs is not None:
        final_sig = sig_figs
    elif pf_sig is not None:
        final_sig = pf_sig
    else:
        final_sig = None

    if final_sig is not None:
        result_value = _apply_sig_figs(result_value, final_sig)

    return Quantity(result_value, target, sig_figs=final_sig)


def make_quantity(
    value: Decimal | int | float | str,
    unit_symbol: str,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Create a Quantity from a value and unit symbol.

    Args:
        value: The numeric value.
        unit_symbol: The unit symbol (e.g., "kW", "°C").
        sig_figs: Optional significant figures.

    Returns:
        A new Quantity instance.
    """
    if isinstance(value, str):
        try:
            value = Decimal(value)
        except Exception:
            raise TypeError(f"Cannot create Quantity from {type(value).__name__}")
    elif isinstance(value, (int, float)):
        value = Decimal(str(value))
    if not isinstance(value, Decimal):
        raise TypeError(f"Cannot create Quantity from {type(value).__name__}")
    unit = UNIT_REGISTRY.get(unit_symbol)
    return Quantity(value, unit, sig_figs=sig_figs)


def format_quantity(
    quantity: Quantity,
    *,
    decimal_places: int | None = None,
    use_si_prefix: bool = False,
) -> str:
    """Format a quantity as a human-readable string.

    Args:
        quantity: The quantity to format.
        decimal_places: Fixed decimal places (None = auto).
        use_si_prefix: Whether to use SI prefix formatting.

    Returns:
        Formatted string like "1.50 kW" or "25.0 °C".
    """
    if decimal_places is not None:
        val = quantity.value.quantize(
            Decimal(1).scaleb(-decimal_places), rounding=ROUND_HALF_UP
        )
    else:
        val = quantity.value

    if use_si_prefix and quantity.unit.dimension in (Dimension.POWER, Dimension.ENERGY):
        return _format_with_si_prefix(quantity)

    return f"{val} {quantity.unit.symbol}"


def _format_with_si_prefix(quantity: Quantity) -> str:
    """Format using appropriate SI prefix."""
    base = quantity.to_base()
    val = base.value

    if val == 0:
        return f"0 {quantity.unit.symbol}"

    abs_val = abs(val)
    unit = quantity.unit

    if unit.dimension == Dimension.POWER:
        if abs_val >= Decimal(1_000_000_000):
            return f"{val / Decimal(1_000_000_000)} GW"
        elif abs_val >= Decimal(1_000_000):
            return f"{val / Decimal(1_000_000)} MW"
        elif abs_val >= Decimal(1000):
            return f"{val / Decimal(1000)} kW"
        else:
            return f"{val} W"
    elif unit.dimension == Dimension.ENERGY:
        if abs_val >= Decimal(1_000_000_000):
            return f"{val / Decimal(1_000_000_000)} GWh"
        elif abs_val >= Decimal(1_000_000):
            return f"{val / Decimal(1_000_000)} MWh"
        elif abs_val >= Decimal(1000):
            return f"{val / Decimal(1000)} kWh"
        else:
            return f"{val} Wh"

    return f"{val} {unit.symbol}"


# === Convenience functions for common conversions ===

def kw_to_mw(kw: Decimal | int | float, *, sig_figs: int | None = None) -> Quantity:
    """Convert kilowatts to megawatts."""
    return make_quantity(kw, "kW", sig_figs=sig_figs).to("MW")


def mw_to_kw(mw: Decimal | int | float, *, sig_figs: int | None = None) -> Quantity:
    """Convert megawatts to kilowatts."""
    return make_quantity(mw, "MW", sig_figs=sig_figs).to("kW")


def kwh_to_mwh(kwh: Decimal | int | float, *, sig_figs: int | None = None) -> Quantity:
    """Convert kilowatt-hours to megawatt-hours."""
    return make_quantity(kwh, "kWh", sig_figs=sig_figs).to("MWh")


def mwh_to_kwh(mwh: Decimal | int | float, *, sig_figs: int | None = None) -> Quantity:
    """Convert megawatt-hours to kilowatt-hours."""
    return make_quantity(mwh, "MWh", sig_figs=sig_figs).to("kWh")


def c_to_f(c: Decimal | int | float, *, sig_figs: int | None = None) -> Quantity:
    """Convert Celsius to Fahrenheit."""
    return convert_temperature(c, "C", "F", sig_figs=sig_figs)


def f_to_c(f: Decimal | int | float, *, sig_figs: int | None = None) -> Quantity:
    """Convert Fahrenheit to Celsius."""
    return convert_temperature(f, "F", "C", sig_figs=sig_figs)


def va_to_w(
    va: Decimal | int | float,
    power_factor: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert volt-amperes to watts."""
    return convert_with_power_factor(va, "VA", "W", power_factor, sig_figs=sig_figs)


def w_to_va(
    w: Decimal | int | float,
    power_factor: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert watts to volt-amperes."""
    return convert_with_power_factor(w, "W", "VA", power_factor, sig_figs=sig_figs)


def kva_to_kw(
    kva: Decimal | int | float,
    power_factor: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert kilovolt-amperes to kilowatts."""
    return convert_with_power_factor(kva, "kVA", "kW", power_factor, sig_figs=sig_figs)


def kw_to_kva(
    kw: Decimal | int | float,
    power_factor: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert kilowatts to kilovolt-amperes."""
    return convert_with_power_factor(kw, "kW", "kVA", power_factor, sig_figs=sig_figs)


def va_to_kva(
    va: Decimal | int | float,
    power_factor: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Convert volt-amperes to kilovolt-amperes."""
    return convert_with_power_factor(va, "VA", "kVA", power_factor, sig_figs=sig_figs)


def compute_pue(
    total_facility_power: Decimal | int | float,
    it_equipment_power: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Decimal:
    """Compute Power Usage Effectiveness (PUE).

    PUE = Total Facility Power / IT Equipment Power
    """
    if isinstance(total_facility_power, (int, float)):
        total_facility_power = Decimal(str(total_facility_power))
    if isinstance(it_equipment_power, (int, float)):
        it_equipment_power = Decimal(str(it_equipment_power))

    if it_equipment_power <= 0:
        raise ValueError("IT equipment power must be positive")

    pue = total_facility_power / it_equipment_power

    if sig_figs is not None:
        pue = _apply_sig_figs(pue, sig_figs)

    return pue


def compute_dcime(
    it_equipment_power: Decimal | int | float,
    total_facility_power: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Decimal:
    """Compute Data Center Infrastructure Efficiency (DCiE).

    DCiE = IT Equipment Power / Total Facility Power = 1 / PUE
    """
    if isinstance(it_equipment_power, (int, float)):
        it_equipment_power = Decimal(str(it_equipment_power))
    if isinstance(total_facility_power, (int, float)):
        total_facility_power = Decimal(str(total_facility_power))

    if total_facility_power <= 0:
        raise ValueError("Total facility power must be positive")

    dcie = it_equipment_power / total_facility_power

    if sig_figs is not None:
        dcie = _apply_sig_figs(dcie, sig_figs)

    return dcie


def compute_carbon_emissions(
    energy_kwh: Decimal | int | float,
    carbon_factor_kg_per_kwh: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Compute carbon emissions from energy consumption.

    Returns:
        Quantity in kg CO2.
    """
    if isinstance(energy_kwh, (int, float)):
        energy_kwh = Decimal(str(energy_kwh))
    if isinstance(carbon_factor_kg_per_kwh, (int, float)):
        carbon_factor_kg_per_kwh = Decimal(str(carbon_factor_kg_per_kwh))

    emissions = energy_kwh * carbon_factor_kg_per_kwh

    e_sig = _count_sig_figs(energy_kwh)
    cf_sig = _count_sig_figs(carbon_factor_kg_per_kwh)
    if e_sig is not None and cf_sig is not None:
        sig = min(e_sig, cf_sig)
    elif e_sig is not None:
        sig = e_sig
    elif cf_sig is not None:
        sig = cf_sig
    else:
        sig = sig_figs

    if sig is not None:
        emissions = _apply_sig_figs(emissions, sig)

    return Quantity(emissions, UNIT_REGISTRY.get("kg"), sig_figs=sig)


def compute_energy_from_power(
    power: Quantity,
    duration_hours: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Compute energy consumption from power and duration.

    Args:
        power: Power quantity (e.g., kW).
        duration_hours: Duration in hours.
        sig_figs: Optional significant figures.

    Returns:
        Energy quantity in kWh (if power is in kW) or matching unit.
    """
    if isinstance(duration_hours, (int, float)):
        duration_hours = Decimal(str(duration_hours))

    if duration_hours < 0:
        raise ValueError("Duration must be non-negative")

    power_kw = power.to("kW")
    energy_kwh = power_kw.value * duration_hours

    dur_sig = _count_sig_figs(duration_hours)
    if power.sig_figs is not None and dur_sig is not None:
        sig = min(power.sig_figs, dur_sig)
    elif power.sig_figs is not None:
        sig = power.sig_figs
    elif dur_sig is not None:
        sig = dur_sig
    else:
        sig = sig_figs

    if sig is not None:
        energy_kwh = _apply_sig_figs(energy_kwh, sig)

    return Quantity(energy_kwh, UNIT_REGISTRY.get("kWh"), sig_figs=sig)


def compute_power_from_energy(
    energy: Quantity,
    duration_hours: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Compute average power from energy and duration.

    Args:
        energy: Energy quantity (e.g., kWh).
        duration_hours: Duration in hours.
        sig_figs: Optional significant figures.

    Returns:
        Power quantity in kW (if energy is in kWh) or matching unit.
    """
    if isinstance(duration_hours, (int, float)):
        duration_hours = Decimal(str(duration_hours))

    if duration_hours <= 0:
        raise ValueError("Duration must be positive")

    energy_kwh = energy.to("kWh")
    power_kw = energy_kwh.value / duration_hours

    dur_sig = _count_sig_figs(duration_hours)
    if energy.sig_figs is not None and dur_sig is not None:
        sig = min(energy.sig_figs, dur_sig)
    elif energy.sig_figs is not None:
        sig = energy.sig_figs
    elif dur_sig is not None:
        sig = dur_sig
    else:
        sig = sig_figs

    if sig is not None:
        power_kw = _apply_sig_figs(power_kw, sig)

    return Quantity(power_kw, UNIT_REGISTRY.get("kW"), sig_figs=sig)


def compute_cooling_load(
    heat_load_kw: Decimal | int | float,
    cop: Decimal | int | float,
    *,
    sig_figs: int | None = None,
) -> Quantity:
    """Compute cooling electrical load from heat load and COP.

    Cooling Power = Heat Load / COP

    Args:
        heat_load_kw: Heat load in kW.
        cop: Coefficient of Performance (dimensionless, > 0).
        sig_figs: Optional significant figures.

    Returns:
        Cooling power quantity in kW.
    """
    if isinstance(heat_load_kw, (int, float)):
        heat_load_kw = Decimal(str(heat_load_kw))
    if isinstance(cop, (int, float)):
        cop = Decimal(str(cop))

    if cop <= 0:
        raise ValueError("COP must be positive")

    cooling_power = heat_load_kw / cop

    hl_sig = _count_sig_figs(heat_load_kw)
    cop_sig = _count_sig_figs(cop)
    if hl_sig is not None and cop_sig is not None:
        sig = min(hl_sig, cop_sig)
    elif hl_sig is not None:
        sig = hl_sig
    elif cop_sig is not None:
        sig = cop_sig
    else:
        sig = sig_figs

    if sig is not None:
        cooling_power = _apply_sig_figs(cooling_power, sig)

    return Quantity(cooling_power, UNIT_REGISTRY.get("kW"), sig_figs=sig)


def compute_ups_runtime(
    battery_capacity_kwh: Decimal | int | float,
    load_kw: Decimal | int | float,
    *,
    efficiency: Decimal | int | float = Decimal("0.95"),
    sig_figs: int | None = None,
) -> Quantity:
    """Estimate UPS runtime from battery capacity and load.

    Runtime = (Battery Capacity * Efficiency) / Load

    Args:
        battery_capacity_kwh: Battery capacity in kWh.
        load_kw: Load in kW.
        efficiency: UPS efficiency (0 < eff <= 1), default 0.95.
        sig_figs: Optional significant figures.

    Returns:
        Runtime quantity in hours.
    """
    if isinstance(battery_capacity_kwh, (int, float)):
        battery_capacity_kwh = Decimal(str(battery_capacity_kwh))
    if isinstance(load_kw, (int, float)):
        load_kw = Decimal(str(load_kw))
    if isinstance(efficiency, (int, float)):
        efficiency = Decimal(str(efficiency))

    if load_kw <= 0:
        raise ValueError("Load must be positive")
    if efficiency <= 0 or efficiency > 1:
        raise ValueError("Efficiency must be in (0, 1]")

    runtime = (battery_capacity_kwh * efficiency) / load_kw

    cap_sig = _count_sig_figs(battery_capacity_kwh)
    load_sig = _count_sig_figs(load_kw)
    eff_sig = _count_sig_figs(efficiency)
    sigs = [s for s in [cap_sig, load_sig, eff_sig] if s is not None]
    sig = min(sigs) if sigs else sig_figs

    if sig is not None:
        runtime = _apply_sig_figs(runtime, sig)

    return Quantity(runtime, UNIT_REGISTRY.get("h"), sig_figs=sig)


# === Batch conversion support ===

def convert_many(
    quantities: list[Quantity],
    target_unit: Unit | str,
) -> list[Quantity]:
    """Convert multiple quantities to the same target unit."""
    return [convert(q, target_unit) for q in quantities]


def normalize_to_base(
    quantities: list[Quantity],
) -> list[Quantity]:
    """Convert a list of quantities to their respective base units."""
    return [q.to_base() for q in quantities]


# === Validation helpers ===

def validate_same_dimension(*quantities: Quantity) -> bool:
    """Check that all quantities have the same dimension."""
    if not quantities:
        return True
    dim = quantities[0].unit.dimension
    return all(q.unit.dimension == dim for q in quantities)


def validate_range(
    quantity: Quantity,
    min_value: Decimal | int | float | None = None,
    max_value: Decimal | int | float | None = None,
) -> bool:
    """Check that a quantity's value is within a range."""
    if min_value is not None:
        if isinstance(min_value, (int, float)):
            min_value = Decimal(str(min_value))
        if quantity.value < min_value:
            return False
    if max_value is not None:
        if isinstance(max_value, (int, float)):
            max_value = Decimal(str(max_value))
        if quantity.value > max_value:
            return False
    return True


def assert_same_dimension(*quantities: Quantity) -> None:
    """Assert that all quantities have the same dimension."""
    if not validate_same_dimension(*quantities):
        dims = [q.unit.dimension.value for q in quantities]
        raise ValueError(f"Quantities have different dimensions: {dims}")
