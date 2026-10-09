import os, sys, shutil

MOBILE = r"C:\woffy-mobile"

# ============================================================
# 1) Funciones en services/admin.ts
# ============================================================
SERVICE_PATH = os.path.join(MOBILE, "src", "services", "admin.ts")
with open(SERVICE_PATH, "rb") as f:
    svc = f.read()

if b"getAdminStats" in svc:
    print("[SKIP] service ya tiene stats/actions")
else:
    add = """

// ============================================
// Estadisticas y auditoria
// ============================================

export interface AdminStats {
  users_total: number;
  users_active: number;
  users_owners: number;
  users_walkers: number;
  users_admins: number;
  walkers_online_now: number;
  walks_total: number;
  walks_pending: number;
  walks_accepted: number;
  walks_in_progress: number;
  walks_completed: number;
  walks_cancelled: number;
  walks_today: number;
  walks_this_month: number;
  revenue_total: string;
  revenue_this_month: string;
  escrow_pending_total: string;
  disputed_total: string;
  flagged_walks: number;
  disputed_payments: number;
}

export interface AdminAction {
  id: number;
  admin_id: number | null;
  admin_email: string;
  action: string;
  target_type: string;
  target_id: number | null;
  description: string;
  created_at: string;
}

export async function getAdminStats(): Promise<AdminStats> {
  const res = await api.get<AdminStats>("/admin/stats");
  return res.data;
}

export async function getAdminActions(params?: {
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<AdminAction[]> {
  const query = new URLSearchParams();
  if (params?.action) query.append("action", params.action);
  if (params?.limit) query.append("limit", String(params.limit));
  if (params?.offset) query.append("offset", String(params.offset));
  const qs = query.toString();
  const res = await api.get<AdminAction[]>(`/admin/actions${qs ? "?" + qs : ""}`);
  return res.data;
}
"""
    svc = svc.rstrip() + add.encode("utf-8")
    with open(SERVICE_PATH, "wb") as f:
        f.write(svc)
    print("[OK] Funciones agregadas al service")

# ============================================================
# 2) AdminStatsScreen.tsx
# ============================================================
STATS_SCREEN = r'''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { getAdminStats, AdminStats } from "../services/admin";
import { spacing, radius, shadows } from "../theme/colors";

function formatMoney(v: string | number): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  return "$" + n.toFixed(0).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function AdminStatsScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const styles = makeStyles(colors, insets.bottom);

  const [stats, setStats] = useState<AdminStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getAdminStats();
      setStats(data);
    } catch (e: any) {
      console.warn("[stats] error:", e?.message);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  if (loading || !stats) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      refreshControl={
        <RefreshControl
          refreshing={refreshing}
          onRefresh={() => load(true)}
          tintColor={colors.accent}
        />
      }
      showsVerticalScrollIndicator={false}
    >
      <Text style={styles.sectionTitle}>USUARIOS</Text>
      <View style={styles.grid}>
        <View style={styles.tile}>
          <Text style={styles.tileValue}>{stats.users_total}</Text>
          <Text style={styles.tileLabel}>TOTALES</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#10B981" }]}>{stats.users_active}</Text>
          <Text style={styles.tileLabel}>ACTIVOS</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#3B82F6" }]}>{stats.users_owners}</Text>
          <Text style={styles.tileLabel}>DUEÑOS</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#10B981" }]}>{stats.users_walkers}</Text>
          <Text style={styles.tileLabel}>PASEADORES</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#C9A961" }]}>{stats.walkers_online_now}</Text>
          <Text style={styles.tileLabel}>ONLINE AHORA</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>PASEOS</Text>
      <View style={styles.grid}>
        <View style={styles.tile}>
          <Text style={styles.tileValue}>{stats.walks_total}</Text>
          <Text style={styles.tileLabel}>TOTALES</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#10B981" }]}>{stats.walks_completed}</Text>
          <Text style={styles.tileLabel}>COMPLETADOS</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#F59E0B" }]}>{stats.walks_pending}</Text>
          <Text style={styles.tileLabel}>PENDIENTES</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#B91C1C" }]}>{stats.walks_cancelled}</Text>
          <Text style={styles.tileLabel}>CANCELADOS</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#C9A961" }]}>{stats.walks_today}</Text>
          <Text style={styles.tileLabel}>HOY</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#C9A961" }]}>{stats.walks_this_month}</Text>
          <Text style={styles.tileLabel}>ESTE MES</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>INGRESOS</Text>
      <View style={styles.moneyCard}>
        <View style={styles.moneyRow}>
          <Text style={styles.moneyLabel}>Comision total</Text>
          <Text style={styles.moneyValue}>{formatMoney(stats.revenue_total)}</Text>
        </View>
        <View style={styles.moneyRow}>
          <Text style={styles.moneyLabel}>Comision este mes</Text>
          <Text style={styles.moneyValue}>{formatMoney(stats.revenue_this_month)}</Text>
        </View>
        <View style={styles.moneyRow}>
          <Text style={styles.moneyLabel}>En escrow ahora</Text>
          <Text style={[styles.moneyValue, { color: "#F59E0B" }]}>
            {formatMoney(stats.escrow_pending_total)}
          </Text>
        </View>
        <View style={styles.moneyRow}>
          <Text style={styles.moneyLabel}>En disputa</Text>
          <Text style={[styles.moneyValue, { color: "#F87171" }]}>
            {formatMoney(stats.disputed_total)}
          </Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>MODERACION</Text>
      <View style={styles.grid}>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#F87171" }]}>{stats.flagged_walks}</Text>
          <Text style={styles.tileLabel}>PASEOS MARCADOS</Text>
        </View>
        <View style={styles.tile}>
          <Text style={[styles.tileValue, { color: "#F87171" }]}>{stats.disputed_payments}</Text>
          <Text style={styles.tileLabel}>DISPUTAS ABIERTAS</Text>
        </View>
      </View>

      <TouchableOpacity
        style={styles.actionLink}
        onPress={() => navigation.navigate("AdminActions")}
        activeOpacity={0.85}
      >
        <Text style={styles.actionLinkText}>Ver historial de acciones admin</Text>
        <Text style={styles.actionLinkArrow}>{">"}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const makeStyles = (colors: any, insetBottom: number) =>
  StyleSheet.create({
    center: {
      flex: 1,
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: colors.background,
    },
    container: {
      flexGrow: 1,
      backgroundColor: colors.background,
      padding: spacing.md,
      paddingBottom: (insetBottom || 0) + 40,
    },
    sectionTitle: {
      fontSize: 11,
      fontWeight: "800",
      color: colors.textMuted,
      letterSpacing: 1,
      marginTop: spacing.md,
      marginBottom: spacing.sm,
    },
    grid: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: spacing.sm,
    },
    tile: {
      width: "31%",
      aspectRatio: 1,
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.sm,
      alignItems: "center",
      justifyContent: "center",
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    tileValue: { fontSize: 26, fontWeight: "900", color: colors.text },
    tileLabel: { fontSize: 9, fontWeight: "800", color: colors.textMuted, marginTop: 2, letterSpacing: 0.4, textAlign: "center" },
    moneyCard: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.md,
      borderWidth: 1,
      borderColor: colors.accent,
      ...shadows.card,
    },
    moneyRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      paddingVertical: 6,
    },
    moneyLabel: { fontSize: 13, color: colors.textMuted },
    moneyValue: { fontSize: 15, fontWeight: "800", color: colors.accent },
    actionLink: {
      marginTop: spacing.lg,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      borderWidth: 1,
      borderColor: colors.border,
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      ...shadows.card,
    },
    actionLinkText: { fontSize: 14, fontWeight: "700", color: colors.text },
    actionLinkArrow: { fontSize: 20, color: colors.accent },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminStatsScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(STATS_SCREEN)
print("[OK] screens/AdminStatsScreen.tsx")

# ============================================================
# 3) AdminActionsScreen.tsx
# ============================================================
ACTIONS_SCREEN = r'''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
} from "react-native";
import { useFocusEffect } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { getAdminActions, AdminAction } from "../services/admin";
import { spacing, radius, shadows } from "../theme/colors";

const FILTERS = [
  { key: "todas", label: "TODAS" },
  { key: "user_block", label: "BLOQUEOS" },
  { key: "dispute_resolve", label: "DISPUTAS" },
  { key: "flag_clear", label: "FLAGS" },
];

const ACTION_ICONS: Record<string, string> = {
  user_block: "\u{1F6AB}",       // 🚫
  user_unblock: "\u2705",        // ✅
  dispute_resolve: "\u2696",     // ⚖
  flag_clear: "\u{1F3F4}",       // 🏴
};

const ACTION_COLORS: Record<string, string> = {
  user_block: "#F87171",
  user_unblock: "#10B981",
  dispute_resolve: "#C9A961",
  flag_clear: "#3B82F6",
};

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    const argMs = d.getTime() - 3 * 60 * 60 * 1000;
    const arg = new Date(argMs);
    const dd = String(arg.getUTCDate()).padStart(2, "0");
    const mm = String(arg.getUTCMonth() + 1).padStart(2, "0");
    const yy = arg.getUTCFullYear();
    const hh = String(arg.getUTCHours()).padStart(2, "0");
    const mn = String(arg.getUTCMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${yy} ${hh}:${mn}`;
  } catch {
    return iso;
  }
}

export function AdminActionsScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const styles = makeStyles(colors, insets.bottom);

  const [items, setItems] = useState<AdminAction[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("todas");

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getAdminActions({
        action: filter === "todas" ? undefined : filter,
        limit: 100,
      });
      setItems(data);
    } catch (e: any) {
      console.warn("[actions] error:", e?.message);
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
              <Text style={styles.emptyTitle}>Sin acciones registradas</Text>
              <Text style={styles.emptyText}>
                Cuando un admin haga algo, va a aparecer aca
              </Text>
            </View>
          }
          renderItem={({ item }) => {
            const color = ACTION_COLORS[item.action] || colors.accent;
            const icon = ACTION_ICONS[item.action] || "\u2699";
            return (
              <View style={styles.card}>
                <View style={styles.cardHeader}>
                  <View style={[styles.iconWrap, { backgroundColor: color + "22" }]}>
                    <Text style={styles.iconText}>{icon}</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.cardDescription}>{item.description}</Text>
                    <Text style={styles.cardAdmin}>{item.admin_email}</Text>
                  </View>
                </View>
                <View style={styles.cardFooter}>
                  <Text style={styles.cardDate}>{formatDate(item.created_at)}</Text>
                  <Text style={[styles.cardAction, { color }]}>
                    {item.action.replace("_", " ").toUpperCase()}
                  </Text>
                </View>
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
      flexWrap: "wrap",
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
    emptyText: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs, textAlign: "center" },
    card: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.md,
      marginBottom: spacing.sm,
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    cardHeader: {
      flexDirection: "row",
      alignItems: "center",
      marginBottom: spacing.sm,
    },
    iconWrap: {
      width: 42,
      height: 42,
      borderRadius: 21,
      alignItems: "center",
      justifyContent: "center",
      marginRight: spacing.md,
    },
    iconText: { fontSize: 22 },
    cardDescription: { fontSize: 14, fontWeight: "700", color: colors.text, lineHeight: 20 },
    cardAdmin: { fontSize: 11, color: colors.textMuted, marginTop: 2 },
    cardFooter: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      paddingTop: spacing.sm,
      borderTopWidth: 1,
      borderTopColor: colors.border,
    },
    cardDate: { fontSize: 12, color: colors.textMuted },
    cardAction: { fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminActionsScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(ACTIONS_SCREEN)
print("[OK] screens/AdminActionsScreen.tsx")

# ============================================================
# 4) App.tsx: rutas
# ============================================================
APP_PATH = os.path.join(MOBILE, "App.tsx")
with open(APP_PATH, "rb") as f:
    src = f.read()

if b"AdminStatsScreen" in src:
    print("[SKIP] App.tsx ya tiene rutas")
else:
    viejo = b'import { AdminUserDetailScreen } from "./src/screens/AdminUserDetailScreen";'
    nuevo = (
        viejo + b'\n'
        b'import { AdminStatsScreen } from "./src/screens/AdminStatsScreen";\n'
        b'import { AdminActionsScreen } from "./src/screens/AdminActionsScreen";'
    )
    if viejo not in src:
        print("[FAIL] no encontre import de AdminUserDetailScreen")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    viejo2 = b'<Stack.Screen name="AdminUserDetail" component={AdminUserDetailScreen} options={{ title: "Detalle del usuario" }} />'
    nuevo2 = (
        viejo2 + b'\n'
        b'            <Stack.Screen name="AdminStats" component={AdminStatsScreen} options={{ title: "Estadisticas" }} />\n'
        b'            <Stack.Screen name="AdminActions" component={AdminActionsScreen} options={{ title: "Historial de acciones" }} />'
    )
    if viejo2 not in src:
        print("[FAIL] no encontre Stack.Screen de AdminUserDetail")
        sys.exit(1)
    src = src.replace(viejo2, nuevo2, 1)

    with open(APP_PATH, "wb") as f:
        f.write(src)
    print("[OK] App.tsx actualizado")

# ============================================================
# 5) AdminHomeScreen: agregar botones Stats + Actions
# ============================================================
ADMIN_HOME = os.path.join(MOBILE, "src", "screens", "AdminHomeScreen.tsx")
with open(ADMIN_HOME, "rb") as f:
    src = f.read()

if b"navigate(\"AdminStats\")" in src:
    print("[SKIP] AdminHome ya tiene botones Stats/Actions")
else:
    # Insertar los 2 botones nuevos antes del boton "Reportes de seguridad"
    viejo = '''        <TouchableOpacity
          style={[styles.actionCard, styles.actionCardDisabled]}
          disabled
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F6E1}\\uFE0F"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Reportes de seguridad</Text>
            <Text style={styles.actionSubtitle}>Proximamente</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>'''

    # Botones nuevos
    nuevos = '''        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminStats")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F4CA}"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Estadisticas</Text>
            <Text style={styles.actionSubtitle}>Contadores y metricas</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminActions")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F4DC}"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Historial de acciones</Text>
            <Text style={styles.actionSubtitle}>Auditoria de admins</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>

''' + viejo

    if viejo not in src:
        print("[WARN] no encontre el bloque de Reportes de seguridad, insertando al final")

    src = src.replace(viejo, nuevos, 1)
    with open(ADMIN_HOME, "wb") as f:
        f.write(src)
    print("[OK] Botones Stats y Actions agregados a AdminHome")

print("\n[DONE] Pantallas y botones listos")