"""Reglas de precios de Woffy Go. Unica fuente de verdad en el servidor."""
import math
from decimal import Decimal, ROUND_HALF_UP

WALK_HOURLY_RATE = Decimal("7000")
TRANSPORT_BASE_FEE = Decimal("3500")
TRANSPORT_PER_KM_FEE = Decimal("500")
TRANSPORT_MIN_PRICE = Decimal("5000")
TRANSPORT_EXTRA_PET_FEE = Decimal("1500")

MAX_PETS = 3
PET_MULTIPLIERS = [Decimal("1.00"), Decimal("0.75"), Decimal("0.50")]


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _check_pets(num_pets: int) -> None:
    if not 1 <= num_pets <= MAX_PETS:
        raise ValueError(f"La cantidad de mascotas debe estar entre 1 y {MAX_PETS}")


def walk_price(duration_minutes: int, num_pets: int) -> Decimal:
    """Paseo: 7.000 por hora, proporcional a la duracion, con multiplicadores por mascota."""
    if duration_minutes <= 0:
        raise ValueError("La duracion debe ser mayor a cero")
    _check_pets(num_pets)
    hours = Decimal(duration_minutes) / Decimal(60)
    multiplier_sum = sum(PET_MULTIPLIERS[:num_pets], Decimal("0"))
    return _money(WALK_HOURLY_RATE * hours * multiplier_sum)


def transport_price(distance_km: Decimal | float, num_pets: int) -> Decimal:
    """Pet Taxi: max(5.000, 3.500 + 500 * km_entero_superior) + 1.500 por mascota adicional."""
    if distance_km <= 0:
        raise ValueError("La distancia debe ser mayor a cero")
    _check_pets(num_pets)
    
    # Redondeo de km al entero superior
    km_ceil = Decimal(str(math.ceil(float(distance_km))))
    
    # Calculo base con piso minimo de 5.000
    base_calc = TRANSPORT_BASE_FEE + (km_ceil * TRANSPORT_PER_KM_FEE)
    price_base = max(TRANSPORT_MIN_PRICE, base_calc)
    
    # Recargo fijo por cada mascota extra (a partir de la segunda)
    extra_pets = num_pets - 1
    extra_pets_fee = Decimal(extra_pets) * TRANSPORT_EXTRA_PET_FEE
    
    return _money(price_base + extra_pets_fee)