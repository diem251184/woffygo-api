import os, sys, shutil

MOBILE = r"C:\woffy-mobile"

# ==============================================================
# 1) Crear service admin.ts
# ==============================================================
ADMIN_SERVICE = '''import api from "./api";
import { Walk } from "./walks";

export interface WalkVerification {
  walk_id: number;
  owner_id: number;
  walker_id: number | null;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  duration_minutes_expected: number;
  duration_real_minutes: number | null;
  distance_meters: string | null;
  avg_speed_kmh: number | null;
  flagged: boolean;
  reason: string | null;
}

export async function getFlaggedWalks(): Promise<Walk[]> {
  const res = await api.get<Walk[]>("/admin/walks/flagged");
  return res.data;
}

export async function getWalkVerification(walkId: number): Promise<WalkVerification> {
  const res = await api.get<WalkVerification>(`/admin/walks/${walkId}/verification`);
  return res.data;
}

export async function clearWalkFlag(walkId: number, note?: string): Promise<Walk> {
  const res = await api.post<Walk>(`/admin/walks/${walkId}/clear-flag`, {
    note: note || null,
  });
  return res.data;
}
'''

path = os.path.join(MOBILE, "src", "services", "admin.ts")
os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(ADMIN_SERVICE)
print("[OK] services/admin.ts")

# ==============================================================
# 2) AdminHomeScreen.tsx
# ==============================================================
ADMIN_HOME = '''import React from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
} from "react-native";
import { useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { spacing, radius, shadows } from "../theme/colors";

export function AdminHomeScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const styles = makeStyles(colors, insets.bottom);

  return (
    <ScrollView contentContainerStyle={styles.container} showsVerticalScrollIndicator={false}>
      <View style={styles.header}>
        <Text style={styles.title}>Panel de administrador</Text>
        <Text style={styles.subtitle}>Gestiona paseos, usuarios y reportes</Text>
      </View>

      <View style={styles.actionsColumn}>
        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("FlaggedWalks")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>🚩</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Paseos marcados</Text>
            <Text style={styles.actionSubtitle}>Revisar verificaciones pendientes</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionCard, styles.actionCardDisabled]}
          disabled
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>👥</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Usuarios</Text>
            <Text style={styles.actionSubtitle}>Proximamente</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={[styles.actionCard, styles.actionCardDisabled]}
          disabled
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>🛡️</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Reportes de seguridad</Text>
            <Text style={styles.actionSubtitle}>Proximamente</Text>
          </View>
          <Text style={styles.actionArrow}>›</Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const makeStyles = (colors: any, insetBottom: number) =>
  StyleSheet.create({
    container: {
      flexGrow: 1,
      backgroundColor: colors.background,
      paddingHorizontal: spacing.lg,
      paddingTop: spacing.lg,
      paddingBottom: (insetBottom || 0) + 60,
    },
    header: { marginBottom: spacing.xl },
    title: { fontSize: 28, fontWeight: "800", color: colors.text, letterSpacing: -0.5 },
    subtitle: { fontSize: 14, color: colors.textMuted, marginTop: spacing.xs },
    actionsColumn: { gap: spacing.sm },
    actionCard: {
      flexDirection: "row",
      alignItems: "center",
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.md,
      borderWidth: 1,
      borderColor: colors.border,
      ...shadows.card,
    },
    actionCardDisabled: { opacity: 0.5 },
    actionIconWrap: {
      width: 52,
      height: 52,
      borderRadius: 26,
      backgroundColor: colors.surfaceElevated,
      alignItems: "center",
      justifyContent: "center",
      marginRight: spacing.md,
    },
    actionEmoji: { fontSize: 24 },
    actionTitle: { fontSize: 17, fontWeight: "700", color: colors.text },
    actionSubtitle: { fontSize: 13, color: colors.textMuted, marginTop: 2 },
    actionArrow: { fontSize: 30, color: colors.accent, marginLeft: spacing.sm },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminHomeScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(ADMIN_HOME)
print("[OK] screens/AdminHomeScreen.tsx")

# ==============================================================
# 3) FlaggedWalksScreen.tsx
# ==============================================================
FLAGGED_WALKS = '''import React, { useState, useCallback } from "react";
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
import { useFocusEffect, useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { getFlaggedWalks } from "../services/admin";
import { Walk } from "../services/walks";
import { spacing, radius, shadows } from "../theme/colors";

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mn = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm} ${hh}:${mn}`;
  } catch {
    return iso;
  }
}

export function FlaggedWalksScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const styles = makeStyles(colors, insets.bottom);

  const [walks, setWalks] = useState<Walk[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getFlaggedWalks();
      setWalks(data);
    } catch (e: any) {
      Alert.alert("Error", "No se pudieron cargar los paseos marcados");
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

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color={colors.accent} />
      </View>
    );
  }

  return (
    <FlatList
      data={walks}
      keyExtractor={(item) => String(item.id)}
      contentContainerStyle={
        walks.length === 0 ? styles.emptyContainer : styles.listContainer
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
          <Text style={styles.emptyEmoji}>✅</Text>
          <Text style={styles.emptyTitle}>Sin paseos marcados</Text>
          <Text style={styles.emptyText}>
            No hay paseos pendientes de revisión
          </Text>
        </View>
      }
      renderItem={({ item }) => (
        <TouchableOpacity
          style={styles.card}
          activeOpacity={0.9}
          onPress={() =>
            navigation.navigate("WalkVerification", { walkId: item.id })
          }
        >
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Paseo #{item.id}</Text>
            <View style={styles.flagBadge}>
              <Text style={styles.flagBadgeText}>MARCADO</Text>
            </View>
          </View>

          <Text style={styles.cardAddress} numberOfLines={1}>
            📍 {item.pickup_address}
          </Text>

          <View style={styles.cardMetaRow}>
            <Text style={styles.cardMeta}>⏱ {item.duration_minutes} min</Text>
            <Text style={styles.cardMeta}>
              🐕 {item.pets.map((p) => p.name).join(", ")}
            </Text>
          </View>

          {item.flag_reason ? (
            <View style={styles.reasonBox}>
              <Text style={styles.reasonLabel}>MOTIVO</Text>
              <Text style={styles.reasonText} numberOfLines={2}>
                {item.flag_reason}
              </Text>
            </View>
          ) : null}

          <View style={styles.cardFooter}>
            <Text style={styles.cardDate}>{formatDate(item.finished_at || item.created_at)}</Text>
            <Text style={styles.cardAction}>Revisar ›</Text>
          </View>
        </TouchableOpacity>
      )}
    />
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
    cardHeader: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: spacing.xs,
    },
    cardTitle: { fontSize: 16, fontWeight: "800", color: colors.text },
    flagBadge: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radius.sm,
      backgroundColor: "rgba(185,28,28,0.15)",
    },
    flagBadgeText: { fontSize: 10, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
    cardAddress: { fontSize: 13, color: colors.textMuted, marginTop: 2 },
    cardMetaRow: { flexDirection: "row", gap: spacing.md, marginTop: spacing.xs },
    cardMeta: { fontSize: 12, color: colors.textMuted },
    reasonBox: {
      marginTop: spacing.sm,
      padding: spacing.sm,
      backgroundColor: "rgba(185,28,28,0.08)",
      borderRadius: radius.sm,
      borderLeftWidth: 3,
      borderLeftColor: "#B91C1C",
    },
    reasonLabel: { fontSize: 10, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
    reasonText: { fontSize: 12, color: colors.text, marginTop: 2 },
    cardFooter: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginTop: spacing.sm,
      paddingTop: spacing.sm,
      borderTopWidth: 1,
      borderTopColor: colors.border,
    },
    cardDate: { fontSize: 12, color: colors.textMuted },
    cardAction: { fontSize: 13, fontWeight: "700", color: colors.accent },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "FlaggedWalksScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(FLAGGED_WALKS)
print("[OK] screens/FlaggedWalksScreen.tsx")

# ==============================================================
# 4) WalkVerificationScreen.tsx
# ==============================================================
WALK_VERIFICATION = '''import React, { useState, useCallback } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  ActivityIndicator,
  Alert,
  TextInput,
} from "react-native";
import { useRoute, useNavigation } from "@react-navigation/native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useTheme } from "../contexts/ThemeContext";
import { getWalkVerification, clearWalkFlag, WalkVerification } from "../services/admin";
import { spacing, radius, shadows } from "../theme/colors";

function formatDate(iso: string | null): string {
  if (!iso) return "-";
  try {
    const d = new Date(iso);
    const dd = String(d.getDate()).padStart(2, "0");
    const mm = String(d.getMonth() + 1).padStart(2, "0");
    const hh = String(d.getHours()).padStart(2, "0");
    const mn = String(d.getMinutes()).padStart(2, "0");
    return `${dd}/${mm}/${d.getFullYear()} ${hh}:${mn}`;
  } catch {
    return iso;
  }
}

export function WalkVerificationScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const route = useRoute<any>();
  const navigation = useNavigation<any>();
  const { walkId } = route.params || {};
  const styles = makeStyles(colors, insets.bottom);

  const [data, setData] = useState<WalkVerification | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const v = await getWalkVerification(walkId);
      setData(v);
    } catch (e: any) {
      Alert.alert("Error", "No se pudo cargar la verificación");
      navigation.goBack();
    } finally {
      setLoading(false);
    }
  }, [walkId, navigation]);

  React.useEffect(() => {
    load();
  }, [load]);

  async function handleClear() {
    setProcessing(true);
    try {
      await clearWalkFlag(walkId, note.trim() || undefined);
      Alert.alert("Listo", "Flag limpiado correctamente", [
        { text: "OK", onPress: () => navigation.goBack() },
      ]);
    } catch (e: any) {
      Alert.alert("Error", e?.response?.data?.detail || "No se pudo limpiar el flag");
    } finally {
      setProcessing(false);
    }
  }

  if (loading || !data) {
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
        <Text style={styles.title}>Paseo #{data.walk_id}</Text>
        <View style={styles.statusBadge}>
          <Text style={styles.statusText}>{data.status.toUpperCase()}</Text>
        </View>
      </View>

      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{data.duration_real_minutes ?? "-"}</Text>
          <Text style={styles.statLabel}>MIN REALES</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>
            {data.distance_meters ? (Number(data.distance_meters) / 1000).toFixed(2) : "-"}
          </Text>
          <Text style={styles.statLabel}>KM</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>
            {data.avg_speed_kmh ? data.avg_speed_kmh.toFixed(1) : "-"}
          </Text>
          <Text style={styles.statLabel}>KM/H</Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>DETALLES</Text>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Owner ID:</Text>
          <Text style={styles.detailValue}>{data.owner_id}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Walker ID:</Text>
          <Text style={styles.detailValue}>{data.walker_id ?? "-"}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Duración esperada:</Text>
          <Text style={styles.detailValue}>{data.duration_minutes_expected} min</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Inicio:</Text>
          <Text style={styles.detailValue}>{formatDate(data.started_at)}</Text>
        </View>
        <View style={styles.detailRow}>
          <Text style={styles.detailLabel}>Fin:</Text>
          <Text style={styles.detailValue}>{formatDate(data.finished_at)}</Text>
        </View>
      </View>

      {data.flagged && data.reason ? (
        <View style={styles.flagBox}>
          <Text style={styles.flagTitle}>MOTIVO DE MARCADO</Text>
          <Text style={styles.flagText}>{data.reason}</Text>
        </View>
      ) : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>NOTA DE REVISIÓN (OPCIONAL)</Text>
        <TextInput
          style={styles.input}
          value={note}
          onChangeText={setNote}
          placeholder="Ej: Verificado con el dueño, todo OK"
          placeholderTextColor={colors.textMuted}
          multiline
          numberOfLines={3}
          editable={!processing}
          maxLength={300}
        />
      </View>

      <TouchableOpacity
        style={[styles.clearButton, processing && styles.buttonDisabled]}
        onPress={handleClear}
        disabled={processing}
        activeOpacity={0.85}
      >
        {processing ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.clearButtonText}>Limpiar flag</Text>
        )}
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
      padding: spacing.lg,
      paddingBottom: (insetBottom || 0) + 40,
    },
    header: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: spacing.lg,
    },
    title: { fontSize: 26, fontWeight: "800", color: colors.text, letterSpacing: -0.5 },
    statusBadge: {
      paddingHorizontal: spacing.md,
      paddingVertical: 6,
      borderRadius: radius.sm,
      backgroundColor: colors.surfaceElevated,
      borderWidth: 1,
      borderColor: colors.border,
    },
    statusText: { fontSize: 11, fontWeight: "800", color: colors.textMuted, letterSpacing: 0.5 },
    statsRow: {
      flexDirection: "row",
      gap: spacing.sm,
      marginBottom: spacing.lg,
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
    statLabel: { fontSize: 10, fontWeight: "700", color: colors.textMuted, marginTop: 4, letterSpacing: 0.5 },
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
    detailRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      paddingVertical: 6,
    },
    detailLabel: { fontSize: 13, color: colors.textMuted },
    detailValue: { fontSize: 13, fontWeight: "700", color: colors.text },
    flagBox: {
      backgroundColor: "rgba(185,28,28,0.12)",
      borderRadius: radius.lg,
      padding: spacing.md,
      marginBottom: spacing.md,
      borderWidth: 1,
      borderColor: "#B91C1C",
    },
    flagTitle: { fontSize: 11, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
    flagText: { fontSize: 14, color: colors.text, marginTop: spacing.xs, lineHeight: 20 },
    input: {
      backgroundColor: colors.background,
      borderRadius: radius.sm,
      padding: spacing.md,
      color: colors.text,
      fontSize: 14,
      minHeight: 80,
      textAlignVertical: "top",
      borderWidth: 1,
      borderColor: colors.border,
    },
    clearButton: {
      backgroundColor: "#10B981",
      paddingVertical: spacing.md,
      borderRadius: radius.md,
      alignItems: "center",
      marginTop: spacing.sm,
    },
    clearButtonText: { color: "#FFFFFF", fontSize: 16, fontWeight: "800" },
    buttonDisabled: { opacity: 0.6 },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "WalkVerificationScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(WALK_VERIFICATION)
print("[OK] screens/WalkVerificationScreen.tsx")

# ==============================================================
# 5) Modificar App.tsx para agregar las rutas
# ==============================================================
APP_PATH = os.path.join(MOBILE, "App.tsx")
backup = APP_PATH + ".admin.bak"
if not os.path.exists(backup):
    shutil.copyfile(APP_PATH, backup)
    print("[BACKUP] " + backup)

with open(APP_PATH, "rb") as f:
    src = f.read()

if b"AdminHomeScreen" in src:
    print("[SKIP] App.tsx ya tiene AdminHomeScreen")
else:
    # 5a) Agregar import
    viejo_import = b'import { WalkDetailScreen } from "./src/screens/WalkDetailScreen";'
    nuevo_import = (
        viejo_import + b'\n'
        b'import { AdminHomeScreen } from "./src/screens/AdminHomeScreen";\n'
        b'import { FlaggedWalksScreen } from "./src/screens/FlaggedWalksScreen";\n'
        b'import { WalkVerificationScreen } from "./src/screens/WalkVerificationScreen";'
    )
    if viejo_import not in src:
        print("[WARN] no encontre import de WalkDetailScreen, buscando alternativa")
        # Buscar el ultimo import de screens
        import re
        m = re.search(rb'import \{ \w+Screen \} from "\./src/screens/\w+Screen";', src)
        if m:
            viejo_import = m.group(0)
            nuevo_import = (
                viejo_import + b'\n'
                b'import { AdminHomeScreen } from "./src/screens/AdminHomeScreen";\n'
                b'import { FlaggedWalksScreen } from "./src/screens/FlaggedWalksScreen";\n'
                b'import { WalkVerificationScreen } from "./src/screens/WalkVerificationScreen";'
            )
        else:
            print("[FAIL] no pude insertar imports")
            sys.exit(1)
    src = src.replace(viejo_import, nuevo_import, 1)
    print("[OK] Imports agregados")

    # 5b) Agregar Stack.Screen
    viejo_screen = b'<Stack.Screen name="Chat" component={ChatScreen} options={{ title: "Chat" }} />'
    nuevo_screen = (
        viejo_screen + b'\n'
        b'            <Stack.Screen name="AdminHome" component={AdminHomeScreen} options={{ title: "Panel de admin" }} />\n'
        b'            <Stack.Screen name="FlaggedWalks" component={FlaggedWalksScreen} options={{ title: "Paseos marcados" }} />\n'
        b'            <Stack.Screen name="WalkVerification" component={WalkVerificationScreen} options={{ title: "Verificacion" }} />'
    )
    if viejo_screen not in src:
        print("[FAIL] no encontre Stack.Screen de Chat")
        sys.exit(1)
    src = src.replace(viejo_screen, nuevo_screen, 1)
    print("[OK] Stack.Screen agregados")

    with open(APP_PATH, "wb") as f:
        f.write(src)

# ==============================================================
# 6) Modificar HomeScreen para agregar boton admin
# ==============================================================
HOME_PATH = os.path.join(MOBILE, "src", "screens", "HomeScreen.tsx")
backup = HOME_PATH + ".admin.bak"
if not os.path.exists(backup):
    shutil.copyfile(HOME_PATH, backup)
    print("[BACKUP] " + backup)

with open(HOME_PATH, "rb") as f:
    src = f.read()

if b"isAdmin" in src:
    print("[SKIP] HomeScreen ya tiene isAdmin")
else:
    # 6a) Agregar const isAdmin
    viejo = b'  const isWalker = user?.role === "walker";'
    nuevo = (
        b'  const isWalker = user?.role === "walker";\n'
        b'  const isAdmin = user?.role === "admin";'
    )
    if viejo not in src:
        print("[FAIL] no encontre isWalker en HomeScreen")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    # 6b) Agregar bloque de acciones admin (antes del cierre de ScrollView)
    viejo2 = b'    </ScrollView>\n  );\n}'
    nuevo2 = (
        b'\n'
        b'      {isAdmin && (\n'
        b'        <View style={styles.actionsColumn}>\n'
        b'          <TouchableOpacity\n'
        b'            style={styles.primaryActionCard}\n'
        b'            onPress={() => navigation.navigate("AdminHome")}\n'
        b'            activeOpacity={0.9}\n'
        b'          >\n'
        b'            <View style={styles.primaryActionIconWrap}>\n'
        b'              <Text style={styles.primaryActionEmoji}>\xf0\x9f\x9b\xa1\xef\xb8\x8f</Text>\n'
        b'            </View>\n'
        b'            <View style={{ flex: 1 }}>\n'
        b'              <Text style={styles.primaryActionTitle}>Panel de admin</Text>\n'
        b'              <Text style={styles.primaryActionSubtitle}>Gestionar paseos y usuarios</Text>\n'
        b'            </View>\n'
        b'            <Text style={styles.primaryActionArrow}>\xe2\x80\xba</Text>\n'
        b'          </TouchableOpacity>\n'
        b'        </View>\n'
        b'      )}\n'
        b'    </ScrollView>\n  );\n}'
    )
    if viejo2 not in src:
        print("[FAIL] no encontre cierre del ScrollView en HomeScreen")
        sys.exit(1)
    src = src.replace(viejo2, nuevo2, 1)

    with open(HOME_PATH, "wb") as f:
        f.write(src)
    print("[OK] Boton admin agregado a HomeScreen")

print("\n[DONE] Panel de admin creado!")