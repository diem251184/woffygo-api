from geoalchemy2.shape import to_shape
from geoalchemy2.elements import WKTElement
from app.models.walk_location import WalkLocation

# Agregar propiedades de conveniencia en WalkLocation para compatibilidad
def get_lat(self):
    if hasattr(self, "_lat_cached"):
        return self._lat_cached
    try:
        pt = to_shape(self.location)
        return pt.y
    except Exception:
        return 0.0

def get_lon(self):
    if hasattr(self, "_lon_cached"):
        return self._lon_cached
    try:
        pt = to_shape(self.location)
        return pt.x
    except Exception:
        return 0.0

WalkLocation.latitude = property(get_lat)
WalkLocation.longitude = property(get_lon)
