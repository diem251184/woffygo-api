import os

MOBILE = r"C:\woffy-mobile"

MAP_SCREEN = r'''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from "react-native";
import MapboxGL from "@rnmapbox/maps";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { useLocation } from "../hooks/useLocation";
import {
  getNearbySafetyReports,
  SafetyReport,
  CATEGORY_LABELS,
  CATEGORY_EMOJIS,
  CATEGORY_COLORS,
} from "../services/safetyReports";
import { spacing, radius, shadows } from "../theme/colors";

function daysAgo(iso: string): string {
  try {
    const d = new Date(iso);
    const diffMs = Date.now() - d.getTime();
    const days = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    if (days <= 0) return "hoy";
    if (days === 1) return "hace 1 dia";
    return `hace ${days} dias`;
  } catch {
    return "";
  }
}

export function SafetyReportsMapScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const styles = makeStyles(colors, insets.bottom);

  const { coords, refresh: refreshLocation, loading: locLoading } = useLocation(true);
  const [reports, setReports] = useState<SafetyReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<SafetyReport | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      let c = coords;
      if (!c) {
        c = await refreshLocation();
      }
      if (!c) {
        Alert.alert("Sin ubicacion", "Activa el GPS para ver reportes cercanos");
        setLoading(false);
        return;
      }
      const data = await getNearbySafetyReports(c.latitude, c.longitude, 10);
      setReports(data);
    } catch (e: any) {
      console.warn("[safety-map] error:", e?.message);
    } finally {
      setLoading(false);
    }
  }, [coords, refreshLocation]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const mapCenter = coords
    ? [coords.longitude, coords.latitude]
    : [-64.5569, -31.3690];

  return (
    <View style={styles.container}>
      <MapboxGL.MapView
        style={styles.map}
        styleURL={MapboxGL.StyleURL.Dark}
        logoEnabled={false}
        attributionEnabled={false}
      >
        <MapboxGL.Camera
          centerCoordinate={mapCenter as [number, number]}
          zoomLevel={14}
          animationMode="flyTo"
          animationDuration={600}
        />

        {coords && (
          <MapboxGL.PointAnnotation
            id="my-location"
            coordinate={[coords.longitude, coords.latitude]}
          >
            <View style={styles.myLocationDot} />
          </MapboxGL.PointAnnotation>
        )}

        {reports.map((r) => (
          <MapboxGL.PointAnnotation
            key={String(r.id)}
            id={`report-${r.id}`}
            coordinate={[r.longitude, r.latitude]}
            onSelected={() => setSelected(r)}
          >
            <TouchableOpacity
              style={[
                styles.pin,
                { backgroundColor: CATEGORY_COLORS[r.category] },
              ]}
              activeOpacity={0.85}
              onPress={() => setSelected(r)}
            >
              <Text style={styles.pinEmoji}>
                {CATEGORY_EMOJIS[r.category]}
              </Text>
            </TouchableOpacity>
          </MapboxGL.PointAnnotation>
        ))}
      </MapboxGL.MapView>

      <View style={[styles.headerBar, { paddingTop: (insets.top || 0) + 8 }]}>
        <TouchableOpacity
          style={styles.backBtn}
          onPress={() => navigation.goBack()}
          activeOpacity={0.8}
        >
          <Text style={styles.backText}>{"<"}</Text>
        </TouchableOpacity>
        <Text style={styles.headerTitle}>Zonas de seguridad</Text>
        <TouchableOpacity
          style={styles.refreshBtn}
          onPress={load}
          activeOpacity={0.8}
        >
          <Text style={styles.refreshText}>{"\u21BB"}</Text>
        </TouchableOpacity>
      </View>

      {loading && (
        <View style={styles.loadingOverlay}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      )}

      {!loading && reports.length === 0 && (
        <View style={[styles.emptyBanner, { bottom: (insets.bottom || 0) + 20 }]}>
          <Text style={styles.emptyText}>
            No hay reportes activos cerca tuyo
          </Text>
        </View>
      )}

      {selected && (
        <View style={[styles.card, { bottom: (insets.bottom || 0) + 20 }]}>
          <View style={styles.cardHeader}>
            <View
              style={[
                styles.cardIcon,
                { backgroundColor: CATEGORY_COLORS[selected.category] + "22" },
              ]}
            >
              <Text style={styles.cardEmoji}>
                {CATEGORY_EMOJIS[selected.category]}
              </Text>
            </View>
            <View style={{ flex: 1 }}>
              <Text style={styles.cardCategory}>
                {CATEGORY_LABELS[selected.category]}
              </Text>
              <Text style={styles.cardMeta}>
                {daysAgo(selected.created_at)} {"\u00b7"} {selected.reporter_name}
              </Text>
            </View>
            <TouchableOpacity
              onPress={() => setSelected(null)}
              activeOpacity={0.7}
            >
              <Text style={styles.cardClose}>{"\u2715"}</Text>
            </TouchableOpacity>
          </View>
          {selected.description ? (
            <Text style={styles.cardDescription}>{selected.description}</Text>
          ) : (
            <Text style={styles.cardNoDescription}>
              (Sin descripcion adicional)
            </Text>
          )}
          {selected.verified && (
            <View style={styles.verifiedTag}>
              <Text style={styles.verifiedText}>{"\u2713"} Verificado</Text>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const makeStyles = (colors: any, insetBottom: number) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    map: { flex: 1 },
    headerBar: {
      position: "absolute",
      top: 0,
      left: 0,
      right: 0,
      paddingBottom: 10,
      paddingHorizontal: spacing.md,
      flexDirection: "row",
      alignItems: "center",
      gap: spacing.sm,
      backgroundColor: colors.background + "EE",
    },
    backBtn: {
      width: 40,
      height: 40,
      borderRadius: 20,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border,
      alignItems: "center",
      justifyContent: "center",
    },
    backText: { fontSize: 20, fontWeight: "800", color: colors.text },
    headerTitle: {
      flex: 1,
      fontSize: 17,
      fontWeight: "800",
      color: colors.text,
      textAlign: "center",
    },
    refreshBtn: {
      width: 40,
      height: 40,
      borderRadius: 20,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border,
      alignItems: "center",
      justifyContent: "center",
    },
    refreshText: { fontSize: 20, fontWeight: "800", color: colors.accent },
    myLocationDot: {
      width: 20,
      height: 20,
      borderRadius: 10,
      backgroundColor: "#3B82F6",
      borderWidth: 3,
      borderColor: "#FFFFFF",
      shadowColor: "#000",
      shadowOffset: { width: 0, height: 0 },
      shadowOpacity: 0.4,
      shadowRadius: 4,
      elevation: 5,
    },
    pin: {
      width: 40,
      height: 40,
      borderRadius: 20,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: 3,
      borderColor: "#FFFFFF",
      shadowColor: "#000",
      shadowOffset: { width: 0, height: 2 },
      shadowOpacity: 0.4,
      shadowRadius: 4,
      elevation: 6,
    },
    pinEmoji: { fontSize: 18 },
    loadingOverlay: {
      position: "absolute",
      top: "50%",
      left: 0,
      right: 0,
      alignItems: "center",
    },
    emptyBanner: {
      position: "absolute",
      left: spacing.md,
      right: spacing.md,
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      alignItems: "center",
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    emptyText: { fontSize: 14, color: colors.textMuted },
    card: {
      position: "absolute",
      left: spacing.md,
      right: spacing.md,
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.md,
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    cardHeader: {
      flexDirection: "row",
      alignItems: "center",
      marginBottom: spacing.sm,
    },
    cardIcon: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: "center",
      justifyContent: "center",
      marginRight: spacing.md,
    },
    cardEmoji: { fontSize: 20 },
    cardCategory: { fontSize: 15, fontWeight: "800", color: colors.text },
    cardMeta: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
    cardClose: { fontSize: 18, color: colors.textMuted, padding: 4 },
    cardDescription: {
      fontSize: 13,
      color: colors.text,
      lineHeight: 18,
      marginTop: spacing.xs,
    },
    cardNoDescription: {
      fontSize: 12,
      color: colors.textMuted,
      fontStyle: "italic",
      marginTop: spacing.xs,
    },
    verifiedTag: {
      marginTop: spacing.sm,
      alignSelf: "flex-start",
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radius.sm,
      backgroundColor: "rgba(16,185,129,0.15)",
    },
    verifiedText: { fontSize: 10, fontWeight: "800", color: "#10B981", letterSpacing: 0.5 },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "SafetyReportsMapScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(MAP_SCREEN)
print("[OK] screens/SafetyReportsMapScreen.tsx")

print("[DONE]")