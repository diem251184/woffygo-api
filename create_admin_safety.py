import os

MOBILE = r"C:\woffy-mobile"

SCREEN = r'''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import {
  getAdminSafetyReports,
  verifySafetyReport,
  deleteSafetyReport,
  SafetyReportAdmin,
  CATEGORY_LABELS,
  CATEGORY_EMOJIS,
  CATEGORY_COLORS,
} from "../services/safetyReports";
import { spacing, radius, shadows } from "../theme/colors";

const FILTERS = [
  { key: "active", label: "ACTIVOS" },
  { key: "deleted", label: "ELIMINADOS" },
];

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    const argMs = d.getTime() - 3 * 60 * 60 * 1000;
    const arg = new Date(argMs);
    const dd = String(arg.getUTCDate()).padStart(2, "0");
    const mm = String(arg.getUTCMonth() + 1).padStart(2, "0");
    const hh = String(arg.getUTCHours()).padStart(2, "0");
    const mn = String(arg.getUTCMinutes()).padStart(2, "0");
    return `${dd}/${mm} ${hh}:${mn}`;
  } catch {
    return iso;
  }
}

export function AdminSafetyReportsScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const styles = makeStyles(colors, insets.bottom);

  const [items, setItems] = useState<SafetyReportAdmin[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("active");
  const [processingId, setProcessingId] = useState<number | null>(null);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getAdminSafetyReports(filter === "deleted");
      setItems(data);
    } catch (e: any) {
      Alert.alert("Error", "No se pudieron cargar los reportes");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  async function handleVerify(r: SafetyReportAdmin) {
    setProcessingId(r.id);
    try {
      const updated = await verifySafetyReport(r.id);
      setItems((prev) => prev.map((it) => (it.id === r.id ? updated : it)));
    } catch (e: any) {
      Alert.alert("Error", "No se pudo verificar");
    } finally {
      setProcessingId(null);
    }
  }

  function confirmDelete(r: SafetyReportAdmin) {
    Alert.alert(
      "Eliminar reporte",
      `¿Seguro que querés eliminar el reporte #${r.id}?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Eliminar",
          style: "destructive",
          onPress: async () => {
            setProcessingId(r.id);
            try {
              await deleteSafetyReport(r.id, "Eliminado desde panel admin");
              await load();
            } catch (e: any) {
              Alert.alert("Error", "No se pudo eliminar");
            } finally {
              setProcessingId(null);
            }
          },
        },
      ]
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.filtersBar}>
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f.key}
            style={[styles.chip, filter === f.key && styles.chipActive]}
            onPress={() => setFilter(f.key)}
            activeOpacity={0.8}
          >
            <Text style={[styles.chipText, filter === f.key && styles.chipTextActive]}>
              {f.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={items}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={
            items.length === 0 ? styles.emptyContainer : styles.listContainer
          }
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => load(true)}
              tintColor={colors.accent}
            />
          }
          ListEmptyComponent={
            <View style={styles.empty}>
              <Text style={styles.emptyTitle}>Sin reportes</Text>
              <Text style={styles.emptyText}>
                {filter === "active"
                  ? "No hay reportes activos"
                  : "No hay reportes eliminados"}
              </Text>
            </View>
          }
          renderItem={({ item }) => {
            const catColor = CATEGORY_COLORS[item.category];
            const busy = processingId === item.id;
            return (
              <View style={[styles.card, item.deleted && styles.cardDeleted]}>
                <View style={styles.cardHeader}>
                  <View style={[styles.cardIcon, { backgroundColor: catColor + "22" }]}>
                    <Text style={styles.cardEmoji}>
                      {CATEGORY_EMOJIS[item.category]}
                    </Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.cardCategory}>
                      {CATEGORY_LABELS[item.category]}
                      {item.verified ? "  ✓" : ""}
                    </Text>
                    <Text style={styles.cardMeta}>
                      {item.reporter_name} · {item.reporter_role}
                    </Text>
                  </View>
                  {item.deleted && (
                    <View style={styles.deletedTag}>
                      <Text style={styles.deletedTagText}>ELIMINADO</Text>
                    </View>
                  )}
                </View>

                {item.description ? (
                  <Text style={styles.cardDescription}>{item.description}</Text>
                ) : (
                  <Text style={styles.cardNoDescription}>(Sin descripcion)</Text>
                )}

                <View style={styles.metaRow}>
                  <Text style={styles.metaText}>
                    {item.latitude.toFixed(4)}, {item.longitude.toFixed(4)}
                  </Text>
                  <Text style={styles.metaText}>{formatDate(item.created_at)}</Text>
                </View>

                {item.walk_id && (
                  <Text style={styles.walkRef}>Paseo #{item.walk_id}</Text>
                )}

                {!item.deleted && (
                  <View style={styles.actionsRow}>
                    {!item.verified && (
                      <TouchableOpacity
                        style={[styles.actionBtn, styles.verifyBtn, busy && styles.btnDisabled]}
                        onPress={() => handleVerify(item)}
                        disabled={busy}
                        activeOpacity={0.85}
                      >
                        <Text style={styles.actionBtnText}>
                          {busy ? "..." : "Verificar"}
                        </Text>
                      </TouchableOpacity>
                    )}
                    <TouchableOpacity
                      style={[styles.actionBtn, styles.deleteBtn, busy && styles.btnDisabled]}
                      onPress={() => confirmDelete(item)}
                      disabled={busy}
                      activeOpacity={0.85}
                    >
                      <Text style={styles.deleteBtnText}>Eliminar</Text>
                    </TouchableOpacity>
                  </View>
                )}

                {item.deleted && item.deleted_reason && (
                  <Text style={styles.deletedReason}>
                    Motivo: {item.deleted_reason}
                  </Text>
                )}
              </View>
            );
          }}
        />
      )}
    </View>
  );
}

const makeStyles = (colors: any, insetBottom: number) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    filtersBar: {
      flexDirection: "row",
      paddingHorizontal: spacing.md,
      paddingTop: spacing.md,
      paddingBottom: spacing.sm,
      gap: spacing.xs,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    chip: {
      paddingHorizontal: spacing.md,
      paddingVertical: 6,
      borderRadius: radius.sm,
      backgroundColor: colors.surface,
      borderWidth: 1,
      borderColor: colors.border,
    },
    chipActive: { backgroundColor: colors.primary, borderColor: colors.primary },
    chipText: { fontSize: 11, fontWeight: "800", color: colors.text, letterSpacing: 0.5 },
    chipTextActive: { color: colors.white },
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.background,
    },
    listContainer: { padding: spacing.md, paddingBottom: (insetBottom || 0) + 40 },
    emptyContainer: { flexGrow: 1, justifyContent: "center", alignItems: "center" },
    empty: { alignItems: "center", padding: spacing.lg },
    emptyTitle: { fontSize: 18, fontWeight: "800", color: colors.text },
    emptyText: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
    card: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.md,
      marginBottom: spacing.sm,
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    cardDeleted: { opacity: 0.6 },
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
    deletedTag: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radius.sm,
      backgroundColor: "rgba(120,120,120,0.2)",
    },
    deletedTagText: { fontSize: 9, fontWeight: "800", color: colors.textMuted, letterSpacing: 0.5 },
    cardDescription: {
      fontSize: 13,
      color: colors.text,
      lineHeight: 18,
      marginBottom: spacing.sm,
    },
    cardNoDescription: {
      fontSize: 12,
      color: colors.textMuted,
      fontStyle: "italic",
      marginBottom: spacing.sm,
    },
    metaRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      paddingTop: spacing.sm,
      borderTopWidth: 1,
      borderTopColor: colors.border,
    },
    metaText: { fontSize: 11, color: colors.textMuted },
    walkRef: { fontSize: 11, color: colors.accent, marginTop: 4, fontWeight: "700" },
    actionsRow: {
      flexDirection: "row",
      gap: spacing.sm,
      marginTop: spacing.sm,
    },
    actionBtn: {
      flex: 1,
      paddingVertical: spacing.sm,
      borderRadius: radius.sm,
      alignItems: "center",
    },
    verifyBtn: { backgroundColor: "#10B981" },
    deleteBtn: {
      backgroundColor: "transparent",
      borderWidth: 1,
      borderColor: "#B91C1C",
    },
    actionBtnText: { color: "#FFFFFF", fontWeight: "800", fontSize: 13 },
    deleteBtnText: { color: "#F87171", fontWeight: "800", fontSize: 13 },
    btnDisabled: { opacity: 0.6 },
    deletedReason: {
      fontSize: 11,
      color: colors.textMuted,
      fontStyle: "italic",
      marginTop: spacing.sm,
    },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminSafetyReportsScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(SCREEN)
print("[OK] screens/AdminSafetyReportsScreen.tsx")

print("[DONE]")