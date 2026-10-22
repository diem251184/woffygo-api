from decimal import Decimal, ROUND_HALF_UP

WALK_HOURLY_RATE = Decimal("7000.00")

# Multiplicadores para mascotas en paseo
# 1ra: 100%, 2da: 75%, 3ra: 50%
PET_MULTIPLIERS = [Decimal("1.00"), Decimal("0.75"), Decimal("0.50")]

# Pet Taxi
TRANSPORT_BASE_FEE = Decimal("3500.00")
TRANSPORT_KM_FEE = Decimal("500.00")
TRANSPORT_MIN_PRICE = Decimal("500.00")
TRANSPORT_EXTRA_PET_FEE = Decimal("1500.00")


def walk_price(duration_minutes: int, num_pets: int) -> Decimal:
    """Calcula el precio del paseo según duración y multiplicador por mascota."""
    if duration_minutes <= 0:
        duration_minutes = 60
    if num_pets <= 0:
        num_pets = 1

    multiplier = Decimal("0.00")
    for i in range(min(num_pets, len(PET_MULTIPLIERS))):
        multiplier += PET_MULTIPLIERS[i]

    base_hours = Decimal(duration_minutes) / Decimal(60)
    total = WALK_HOURLY_RATE * base_hours * multiplier
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def transport_price(distance_km: Decimal, num_pets: int) -> Decimal:
    """
    Calcula el precio de Pet Taxi con 2 decimales exactos de distancia.
    Base $3.500 + (km * $500). Minimo $5.000. Mascota extra $1.500.
    Ej: 7.90 km -> 3.500 + (7.90 * 500 = 3.950) = $7.450.
    """
    if distance_km < 0:
        distance_km = Decimal("0.00")
    if num_pets <= 0:
        num_pets = 1

    # Asegurar 2 decimales exactos en los kilómetros
    km_exact = distance_km.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    base_calc = TRANSPORT_BASE_FEE + (km_exact * TRANSPORT_KM_FEE)
    price_base = max(Decimal("5000.00"), base_calc)

    extra_pets = max(0, num_pets - 1)
    extra_pets_fee = Decimal(extra_pets) * TRANSPORT_EXTRA_PET_FEE

    total = price_base + extra_pets_fee
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)