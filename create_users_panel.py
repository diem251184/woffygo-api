import os, sys

MOBILE = r"C:\woffy-mobile"

# ============================================================
# 1) Service admin.ts: agregar funciones de usuarios
# ============================================================
SERVICE_PATH = os.path.join(MOBILE, "src", "services", "admin.ts")
with open(SERVICE_PATH, "rb") as f:
    svc = f.read()

if b"getAdminUsers" in svc:
    print("[SKIP] service ya tiene funciones de users")
else:
    add = """

// ============================================
// Usuarios
// ============================================

export interface AdminUserListItem {
  id: number;
  email: string;
  full_name: string;
  phone: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface AdminWalkerProfileInfo {
  bio: string | null;
  hourly_rate: string;
  search_radius_km: number;
  is_online: boolean;
  rating_avg: string | null;
  total_walks: number;
  current_latitude: number | null;
  current_longitude: number | null;
}

export interface AdminUserDetail extends AdminUserListItem {
  updated_at: string;
  pets_count: number;
  walks_as_owner_count: number;
  walks_as_walker_count: number;
  walker_profile: AdminWalkerProfileInfo | null;
}

export async function getAdminUsers(params?: {
  role?: string;
  is_active?: boolean;
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<AdminUserListItem[]> {
  const query = new URLSearchParams();
  if (params?.role) query.append("role", params.role);
  if (params?.is_active !== undefined) query.append("is_active", String(params.is_active));
  if (params?.search) query.append("search", params.search);
  if (params?.limit) query.append("limit", String(params.limit));
  if (params?.offset) query.append("offset", String(params.offset));
  const qs = query.toString();
  const res = await api.get<AdminUserListItem[]>(`/admin/users${qs ? "?" + qs : ""}`);
  return res.data;
}

export async function getAdminUserDetail(userId: number): Promise<AdminUserDetail> {
  const res = await api.get<AdminUserDetail>(`/admin/users/${userId}`);
  return res.data;
}

export async function toggleUserActive(
  userId: number,
  isActive: boolean
): Promise<AdminUserDetail> {
  const res = await api.post<AdminUserDetail>(
    `/admin/users/${userId}/toggle-active`,
    { is_active: isActive }
  );
  return res.data;
}
"""
    svc = svc.rstrip() + add.encode("utf-8")
    with open(SERVICE_PATH, "wb") as f:
        f.write(svc)
    print("[OK] Funciones agregadas a services/admin.ts")

# ============================================================
# 2) AdminUsersScreen.tsx
# ============================================================
USERS_SCREEN = r'''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  ActivityIndicator,
  RefreshControl,
  Alert,
  TextInput,
} from "react-native";
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { getAdminUsers, AdminUserListItem } from "../services/admin";
import { spacing, radius, shadows } from "../theme/colors";

const ROLES = ["todos", "owner", "walker", "admin"] as const;
type RoleFilter = (typeof ROLES)[number];

const ROLE_LABELS: Record<string, string> = {
  owner: "OWNER",
  walker: "WALKER",
  admin: "ADMIN",
};

const ROLE_COLORS: Record<string, string> = {
  owner: "#3B82F6",
  walker: "#10B981",
  admin: "#C9A961",
};

export function AdminUsersScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const styles = makeStyles(colors, insets.bottom);

  const [users, setUsers] = useState<AdminUserListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [roleFilter, setRoleFilter] = useState<RoleFilter>("todos");
  const [search, setSearch] = useState("");

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getAdminUsers({
        role: roleFilter === "todos" ? undefined : roleFilter,
        search: search.trim() || undefined,
        limit: 100,
      });
      setUsers(data);
    } catch (e: any) {
      Alert.alert("Error", "No se pudieron cargar los usuarios");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [roleFilter, search]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  function onSearchSubmit() {
    load();
  }

  return (
    <View style={styles.container}>
      <View style={styles.filtersBar}>
        <TextInput
          style={styles.searchInput}
          value={search}
          onChangeText={setSearch}
          placeholder="Buscar por email o nombre"
          placeholderTextColor={colors.textMuted}
          onSubmitEditing={onSearchSubmit}
          returnKeyType="search"
          autoCapitalize="none"
        />
        <View style={styles.roleChips}>
          {ROLES.map((r) => (
            <TouchableOpacity
              key={r}
              style={[
                styles.chip,
                roleFilter === r && styles.chipActive,
              ]}
              onPress={() => {
                setRoleFilter(r);
              }}
              activeOpacity={0.8}
            >
              <Text
                style={[
                  styles.chipText,
                  roleFilter === r && styles.chipTextActive,
                ]}
              >
                {r === "todos" ? "TODOS" : ROLE_LABELS[r]}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {loading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.accent} />
        </View>
      ) : (
        <FlatList
          data={users}
          keyExtractor={(item) => String(item.id)}
          contentContainerStyle={
            users.length === 0 ? styles.emptyContainer : styles.listContainer
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
              <Text style={styles.emptyEmoji}>?</Text>
              <Text style={styles.emptyTitle}>Sin usuarios</Text>
              <Text style={styles.emptyText}>
                No hay usuarios que coincidan con los filtros
              </Text>
            </View>
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={[styles.card, !item.is_active && styles.cardInactive]}
              activeOpacity={0.9}
              onPress={() =>
                navigation.navigate("AdminUserDetail", { userId: item.id })
              }
            >
              <View style={styles.cardHeader}>
                <Text style={styles.cardTitle} numberOfLines={1}>
                  {item.full_name}
                </Text>
                <View
                  style={[
                    styles.roleBadge,
                    { backgroundColor: (ROLE_COLORS[item.role] || "#666") + "22" },
                  ]}
                >
                  <Text
                    style={[
                      styles.roleBadgeText,
                      { color: ROLE_COLORS[item.role] || "#666" },
                    ]}
                  >
                    {ROLE_LABELS[item.role] || item.role.toUpperCase()}
                  </Text>
                </View>
              </View>

              <Text style={styles.cardEmail} numberOfLines={1}>
                {item.email}
              </Text>
              <Text style={styles.cardPhone}>Tel: {item.phone}</Text>

              {!item.is_active && (
                <View style={styles.blockedTag}>
                  <Text style={styles.blockedTagText}>BLOQUEADO</Text>
                </View>
              )}
            </TouchableOpacity>
          )}
        />
      )}
    </View>
  );
}

const makeStyles = (colors: any, insetBottom: number) =>
  StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    filtersBar: {
      paddingHorizontal: spacing.md,
      paddingTop: spacing.md,
      paddingBottom: spacing.sm,
      backgroundColor: colors.background,
      borderBottomWidth: 1,
      borderBottomColor: colors.border,
    },
    searchInput: {
      backgroundColor: colors.surface,
      borderRadius: radius.sm,
      padding: spacing.md,
      color: colors.text,
      fontSize: 14,
      borderWidth: 1,
      borderColor: colors.border,
      marginBottom: spacing.sm,
    },
    roleChips: {
      flexDirection: "row",
      gap: spacing.xs,
      flexWrap: "wrap",
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
    emptyEmoji: { fontSize: 56, marginBottom: spacing.md },
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
    cardInactive: { opacity: 0.55 },
    cardHeader: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: spacing.xs,
    },
    cardTitle: { fontSize: 16, fontWeight: "800", color: colors.text, flex: 1, marginRight: spacing.sm },
    roleBadge: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radius.sm,
    },
    roleBadgeText: { fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
    cardEmail: { fontSize: 13, color: colors.textMuted, marginTop: 2 },
    cardPhone: { fontSize: 12, color: colors.textMuted, marginTop: 2 },
    blockedTag: {
      marginTop: spacing.sm,
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radius.sm,
      backgroundColor: "rgba(185,28,28,0.15)",
      alignSelf: "flex-start",
    },
    blockedTagText: { fontSize: 10, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminUsersScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(USERS_SCREEN)
print("[OK] screens/AdminUsersScreen.tsx")

# ============================================================
# 3) AdminUserDetailScreen.tsx
# ============================================================
DETAIL_SCREEN = r'''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
} from "react-native";
import { useRoute, useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { getAdminUserDetail, toggleUserActive, AdminUserDetail } from "../services/admin";
import { spacing, radius, shadows } from "../theme/colors";

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

function formatMoney(v: string | number): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  return "$" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

const ROLE_LABELS: Record<string, string> = {
  owner: "Dueño",
  walker: "Paseador",
  admin: "Admin",
};

export function AdminUserDetailScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const route = useRoute<any>();
  const navigation = useNavigation<any>();
  const { userId } = route.params || {};
  const styles = makeStyles(colors, insets.bottom);

  const [user, setUser] = useState<AdminUserDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const u = await getAdminUserDetail(userId);
      setUser(u);
    } catch (e: any) {
      Alert.alert("Error", "No se pudo cargar el usuario");
      navigation.goBack();
    } finally {
      setLoading(false);
    }
  }, [userId, navigation]);

  React.useEffect(() => {
    load();
  }, [load]);

  function confirmToggle() {
    if (!user) return;
    const accion = user.is_active ? "bloquear" : "desbloquear";
    Alert.alert(
      "Confirmar",
      `Vas a ${accion} a ${user.full_name}. Continuar?`,
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Si, " + accion,
          style: user.is_active ? "destructive" : "default",
          onPress: async () => {
            setProcessing(true);
            try {
              const updated = await toggleUserActive(user.id, !user.is_active);
              setUser(updated);
              Alert.alert("Listo", `Usuario ${accion}do`);
            } catch (e: any) {
              Alert.alert("Error", e?.response?.data?.detail || "No se pudo actualizar");
            } finally {
              setProcessing(false);
            }
          },
        },
      ]
    );
  }

  if (loading || !user) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <ScrollView
      contentContainerStyle={styles.container}
      showsVerticalScrollIndicator={false}
    >
      <View style={styles.header}>
        <Text style={styles.title}>{user.full_name}</Text>
        <View style={[
          styles.statusBadge,
          { backgroundColor: user.is_active ? "rgba(16,185,129,0.15)" : "rgba(185,28,28,0.15)" }
        ]}>
          <Text style={[styles.statusText, { color: user.is_active ? "#10B981" : "#F87171" }]}>
            {user.is_active ? "ACTIVO" : "BLOQUEADO"}
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>DATOS</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>ID:</Text>
          <Text style={styles.rowValue}>#{user.id}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Email:</Text>
          <Text style={styles.rowValue}>{user.email}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Telefono:</Text>
          <Text style={styles.rowValue}>{user.phone}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Rol:</Text>
          <Text style={styles.rowValue}>{ROLE_LABELS[user.role] || user.role}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Registro:</Text>
          <Text style={styles.rowValue}>{formatDate(user.created_at)}</Text>
        </View>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{user.pets_count}</Text>
          <Text style={styles.statLabel}>MASCOTAS</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{user.walks_as_owner_count}</Text>
          <Text style={styles.statLabel}>PASEOS OWNER</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{user.walks_as_walker_count}</Text>
          <Text style={styles.statLabel}>PASEOS WALKER</Text>
        </View>
      </View>

      {user.walker_profile && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>PERFIL DE PASEADOR</Text>
          {user.walker_profile.bio ? (
            <Text style={styles.bioText}>{user.walker_profile.bio}</Text>
          ) : null}
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Tarifa:</Text>
            <Text style={styles.rowValue}>{formatMoney(user.walker_profile.hourly_rate)}/h</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Radio:</Text>
            <Text style={styles.rowValue}>{user.walker_profile.search_radius_km} km</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Rating:</Text>
            <Text style={styles.rowValue}>{user.walker_profile.rating_avg ?? "-"}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Paseos totales:</Text>
            <Text style={styles.rowValue}>{user.walker_profile.total_walks}</Text>
          </View>
          <View style={styles.row}>
            <Text style={styles.rowLabel}>Online:</Text>
            <Text style={styles.rowValue}>{user.walker_profile.is_online ? "Si" : "No"}</Text>
          </View>
          {user.walker_profile.current_latitude && user.walker_profile.current_longitude && (
            <View style={styles.row}>
              <Text style={styles.rowLabel}>Ubicacion:</Text>
              <Text style={styles.rowValue}>
                {user.walker_profile.current_latitude.toFixed(4)}, {user.walker_profile.current_longitude.toFixed(4)}
              </Text>
            </View>
          )}
        </View>
      )}

      {user.role !== "admin" && (
        <TouchableOpacity
          style={[
            user.is_active ? styles.blockButton : styles.unblockButton,
            processing && styles.buttonDisabled,
          ]}
          onPress={confirmToggle}
          disabled={processing}
          activeOpacity={0.85}
        >
          {processing ? (
            <ActivityIndicator color="#FFFFFF" />
          ) : (
            <Text style={styles.toggleButtonText}>
              {user.is_active ? "Bloquear usuario" : "Desbloquear usuario"}
            </Text>
          )}
        </TouchableOpacity>
      )}
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
      padding: spacing.lg,
      paddingBottom: (insetBottom || 0) + 40,
    },
    header: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: spacing.lg,
    },
    title: { fontSize: 24, fontWeight: "800", color: colors.text, flex: 1, marginRight: spacing.sm },
    statusBadge: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radius.sm,
    },
    statusText: { fontSize: 10, fontWeight: "800", letterSpacing: 0.5 },
    section: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.md,
      marginBottom: spacing.md,
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    sectionTitle: {
      fontSize: 11,
      fontWeight: "800",
      color: colors.textMuted,
      letterSpacing: 0.8,
      marginBottom: spacing.sm,
    },
    row: {
      flexDirection: "row",
      justifyContent: "space-between",
      paddingVertical: 6,
    },
    rowLabel: { fontSize: 13, color: colors.textMuted },
    rowValue: { fontSize: 13, fontWeight: "700", color: colors.text, flexShrink: 1, marginLeft: spacing.md, textAlign: "right" },
    bioText: { fontSize: 13, color: colors.text, marginBottom: spacing.sm, fontStyle: "italic", lineHeight: 18 },
    statsRow: {
      flexDirection: "row",
      gap: spacing.sm,
      marginBottom: spacing.md,
    },
    statBox: {
      flex: 1,
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.sm,
      alignItems: "center",
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    statValue: { fontSize: 22, fontWeight: "800", color: colors.text },
    statLabel: { fontSize: 9, fontWeight: "700", color: colors.textMuted, marginTop: 4, letterSpacing: 0.4, textAlign: "center" },
    blockButton: {
      backgroundColor: "#B91C1C",
      paddingVertical: spacing.md,
      borderRadius: radius.md,
      alignItems: "center",
      marginTop: spacing.sm,
    },
    unblockButton: {
      backgroundColor: "#10B981",
      paddingVertical: spacing.md,
      borderRadius: radius.md,
      alignItems: "center",
      marginTop: spacing.sm,
    },
    toggleButtonText: { color: "#FFFFFF", fontSize: 16, fontWeight: "800" },
    buttonDisabled: { opacity: 0.6 },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminUserDetailScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(DETAIL_SCREEN)
print("[OK] screens/AdminUserDetailScreen.tsx")

# ============================================================
# 4) App.tsx: agregar rutas
# ============================================================
APP_PATH = os.path.join(MOBILE, "App.tsx")
with open(APP_PATH, "rb") as f:
    src = f.read()

if b"AdminUsersScreen" in src:
    print("[SKIP] App.tsx ya tiene rutas")
else:
    viejo = b'import { AdminDisputeDetailScreen } from "./src/screens/AdminDisputeDetailScreen";'
    nuevo = (
        viejo + b'\n'
        b'import { AdminUsersScreen } from "./src/screens/AdminUsersScreen";\n'
        b'import { AdminUserDetailScreen } from "./src/screens/AdminUserDetailScreen";'
    )
    if viejo not in src:
        print("[FAIL] no encontre import de AdminDisputeDetailScreen")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    viejo2 = b'<Stack.Screen name="AdminDisputeDetail" component={AdminDisputeDetailScreen} options={{ title: "Resolver disputa" }} />'
    nuevo2 = (
        viejo2 + b'\n'
        b'            <Stack.Screen name="AdminUsers" component={AdminUsersScreen} options={{ title: "Usuarios" }} />\n'
        b'            <Stack.Screen name="AdminUserDetail" component={AdminUserDetailScreen} options={{ title: "Detalle del usuario" }} />'
    )
    if viejo2 not in src:
        print("[FAIL] no encontre Stack.Screen de AdminDisputeDetail")
        sys.exit(1)
    src = src.replace(viejo2, nuevo2, 1)

    with open(APP_PATH, "wb") as f:
        f.write(src)
    print("[OK] App.tsx actualizado")

# ============================================================
# 5) AdminHomeScreen: activar boton Usuarios
# ============================================================
ADMIN_HOME = os.path.join(MOBILE, "src", "screens", "AdminHomeScreen.tsx")
with open(ADMIN_HOME, "rb") as f:
    src = f.read()

if b'AdminUsers' in src:
    print("[SKIP] AdminHome ya tiene boton Usuarios")
else:
    # Reemplazar el bloque de "Usuarios - Proximamente" por uno activo
    viejo = b'''        <TouchableOpacity
          style={[styles.actionCard, styles.actionCardDisabled]}
          disabled
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F465}"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Usuarios</Text>
            <Text style={styles.actionSubtitle}>Proximamente</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>'''

    nuevo = b'''        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("AdminUsers")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u{1F465}"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Usuarios</Text>
            <Text style={styles.actionSubtitle}>Ver, bloquear y desbloquear</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>'''

    if viejo not in src:
        print("[FAIL] no encontre el bloque 'Usuarios - Proximamente'")
        print("Puede que haya diferencias de emoji o espacios. Revisando...")
        idx = src.find(b"Usuarios")
        if idx >= 0:
            print("Contexto:")
            print(src[max(0, idx-100):idx+200].decode('utf-8', errors='replace'))
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    with open(ADMIN_HOME, "wb") as f:
        f.write(src)
    print("[OK] Boton Usuarios activado")

print("\n[DONE] Panel de usuarios creado!")