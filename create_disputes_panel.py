import os, sys

MOBILE = r"C:\woffy-mobile"

# ==============================================================
# 1) Agregar funciones al service admin.ts
# ==============================================================
SERVICE_PATH = os.path.join(MOBILE, "src", "services", "admin.ts")

with open(SERVICE_PATH, "rb") as f:
    svc = f.read()

if b"getDisputedPayments" in svc:
    print("[SKIP] service ya tiene funciones de disputes")
else:
    add = """

// ============================================
// Disputas de pago
// ============================================

export interface Payment {
  id: number;
  walk_id: number;
  payer_id: number;
  amount: string;
  platform_fee: string;
  walker_earnings: string;
  status: string;
  dispute_opened_at: string | null;
  dispute_reason: string | null;
  created_at: string;
}

export async function getDisputedPayments(): Promise<Payment[]> {
  const res = await api.get<Payment[]>("/admin/payments/disputed");
  return res.data;
}

export async function resolveDispute(
  paymentId: number,
  releaseToWalker: boolean,
  note?: string
): Promise<Payment> {
  const res = await api.post<Payment>(
    `/payments/admin/${paymentId}/resolve`,
    {
      release_to_walker: releaseToWalker,
      resolution_note: note || null,
    }
  );
  return res.data;
}
"""
    svc = svc.rstrip() + add.encode("utf-8")
    with open(SERVICE_PATH, "wb") as f:
        f.write(svc)
    print("[OK] Funciones agregadas a services/admin.ts")

# ==============================================================
# 2) AdminDisputesScreen.tsx
# ==============================================================
DISPUTES_SCREEN = r'''import React, { useState, useCallback } from "react";
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
import { getDisputedPayments, Payment } from "../services/admin";
import { spacing, radius, shadows } from "../theme/colors";

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
    return dd + "/" + mm + " " + hh + ":" + mn;
  } catch {
    return iso;
  }
}

function formatMoney(v: string | number): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  return "$" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function AdminDisputesScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const navigation = useNavigation<any>();
  const styles = makeStyles(colors, insets.bottom);

  const [items, setItems] = useState<Payment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    try {
      const data = await getDisputedPayments();
      setItems(data);
    } catch (e: any) {
      Alert.alert("Error", "No se pudieron cargar las disputas");
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
          <Text style={styles.emptyEmoji}>OK</Text>
          <Text style={styles.emptyTitle}>Sin disputas abiertas</Text>
          <Text style={styles.emptyText}>
            No hay pagos pendientes de resolucion
          </Text>
        </View>
      }
      renderItem={({ item }) => (
        <TouchableOpacity
          style={styles.card}
          activeOpacity={0.9}
          onPress={() =>
            navigation.navigate("AdminDisputeDetail", { paymentId: item.id })
          }
        >
          <View style={styles.cardHeader}>
            <Text style={styles.cardTitle}>Pago #{item.id}</Text>
            <View style={styles.disputeBadge}>
              <Text style={styles.disputeBadgeText}>EN DISPUTA</Text>
            </View>
          </View>

          <Text style={styles.cardSub}>Paseo #{item.walk_id}</Text>

          <View style={styles.amountRow}>
            <Text style={styles.amountLabel}>MONTO TOTAL</Text>
            <Text style={styles.amountValue}>{formatMoney(item.amount)}</Text>
          </View>

          {item.dispute_reason ? (
            <View style={styles.reasonBox}>
              <Text style={styles.reasonLabel}>MOTIVO</Text>
              <Text style={styles.reasonText} numberOfLines={2}>
                {item.dispute_reason}
              </Text>
            </View>
          ) : null}

          <View style={styles.cardFooter}>
            <Text style={styles.cardDate}>{formatDate(item.dispute_opened_at)}</Text>
            <Text style={styles.cardAction}>Resolver &gt;</Text>
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
      borderColor: "#B91C1C",
      ...shadows.card,
    },
    cardHeader: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      marginBottom: spacing.xs,
    },
    cardTitle: { fontSize: 16, fontWeight: "800", color: colors.text },
    disputeBadge: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 3,
      borderRadius: radius.sm,
      backgroundColor: "rgba(185,28,28,0.15)",
    },
    disputeBadgeText: { fontSize: 10, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
    cardSub: { fontSize: 12, color: colors.textMuted, marginBottom: spacing.sm },
    amountRow: {
      flexDirection: "row",
      justifyContent: "space-between",
      alignItems: "center",
      paddingVertical: spacing.xs,
      borderTopWidth: 1,
      borderTopColor: colors.border,
      marginTop: spacing.sm,
    },
    amountLabel: { fontSize: 11, fontWeight: "800", color: colors.textMuted, letterSpacing: 0.5 },
    amountValue: { fontSize: 20, fontWeight: "800", color: colors.accent },
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

path = os.path.join(MOBILE, "src", "screens", "AdminDisputesScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(DISPUTES_SCREEN)
print("[OK] screens/AdminDisputesScreen.tsx")

# ==============================================================
# 3) AdminDisputeDetailScreen.tsx
# ==============================================================
DETAIL_SCREEN = r'''import React, { useState, useCallback } from "react";
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
import { getDisputedPayments, resolveDispute, Payment } from "../services/admin";
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
    return dd + "/" + mm + "/" + yy + " " + hh + ":" + mn;
  } catch {
    return iso;
  }
}

function formatMoney(v: string | number): string {
  const n = typeof v === "string" ? parseFloat(v) : v;
  return "$" + n.toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

export function AdminDisputeDetailScreen() {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const route = useRoute<any>();
  const navigation = useNavigation<any>();
  const { paymentId } = route.params || {};
  const styles = makeStyles(colors, insets.bottom);

  const [payment, setPayment] = useState<Payment | null>(null);
  const [loading, setLoading] = useState(true);
  const [processing, setProcessing] = useState(false);
  const [note, setNote] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const all = await getDisputedPayments();
      const found = all.find((p) => p.id === paymentId);
      if (!found) {
        Alert.alert("Error", "No se encontro la disputa");
        navigation.goBack();
        return;
      }
      setPayment(found);
    } catch (e: any) {
      Alert.alert("Error", "No se pudo cargar la disputa");
      navigation.goBack();
    } finally {
      setLoading(false);
    }
  }, [paymentId, navigation]);

  React.useEffect(() => {
    load();
  }, [load]);

  function confirmRelease() {
    Alert.alert(
      "Liberar al walker",
      "El paseador va a recibir su pago. Esta accion no se puede deshacer. Continuar?",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Si, liberar",
          style: "default",
          onPress: () => doResolve(true),
        },
      ]
    );
  }

  function confirmRefund() {
    Alert.alert(
      "Reembolsar al owner",
      "El duenio recupera su dinero. Esta accion no se puede deshacer. Continuar?",
      [
        { text: "Cancelar", style: "cancel" },
        {
          text: "Si, reembolsar",
          style: "destructive",
          onPress: () => doResolve(false),
        },
      ]
    );
  }

  async function doResolve(releaseToWalker: boolean) {
    setProcessing(true);
    try {
      await resolveDispute(paymentId, releaseToWalker, note.trim() || undefined);
      Alert.alert(
        "Disputa resuelta",
        releaseToWalker ? "Pago liberado al walker" : "Pago reembolsado al owner",
        [{ text: "OK", onPress: () => navigation.goBack() }]
      );
    } catch (e: any) {
      Alert.alert("Error", e?.response?.data?.detail || "No se pudo resolver");
    } finally {
      setProcessing(false);
    }
  }

  if (loading || !payment) {
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
        <Text style={styles.title}>Pago #{payment.id}</Text>
        <View style={styles.disputeBadge}>
          <Text style={styles.disputeBadgeText}>EN DISPUTA</Text>
        </View>
      </View>

      <View style={styles.amountBox}>
        <Text style={styles.amountLabel}>MONTO TOTAL</Text>
        <Text style={styles.amountValue}>{formatMoney(payment.amount)}</Text>
        <View style={styles.amountSplit}>
          <Text style={styles.amountSub}>
            Fee plataforma: {formatMoney(payment.platform_fee)}
          </Text>
          <Text style={styles.amountSub}>
            Al walker: {formatMoney(payment.walker_earnings)}
          </Text>
        </View>
      </View>

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>DATOS</Text>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Paseo:</Text>
          <Text style={styles.rowValue}>#{payment.walk_id}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Owner ID:</Text>
          <Text style={styles.rowValue}>{payment.payer_id}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Fecha creacion:</Text>
          <Text style={styles.rowValue}>{formatDate(payment.created_at)}</Text>
        </View>
        <View style={styles.row}>
          <Text style={styles.rowLabel}>Disputa abierta:</Text>
          <Text style={styles.rowValue}>{formatDate(payment.dispute_opened_at)}</Text>
        </View>
      </View>

      {payment.dispute_reason ? (
        <View style={styles.reasonBox}>
          <Text style={styles.reasonTitle}>MOTIVO DE LA DISPUTA</Text>
          <Text style={styles.reasonText}>{payment.dispute_reason}</Text>
        </View>
      ) : null}

      <View style={styles.section}>
        <Text style={styles.sectionTitle}>NOTA DE RESOLUCION (OPCIONAL)</Text>
        <TextInput
          style={styles.input}
          value={note}
          onChangeText={setNote}
          placeholder="Ej: Verificado con el walker, GPS correcto"
          placeholderTextColor={colors.textMuted}
          multiline
          numberOfLines={3}
          editable={!processing}
          maxLength={120}
        />
      </View>

      <TouchableOpacity
        style={[styles.releaseButton, processing && styles.buttonDisabled]}
        onPress={confirmRelease}
        disabled={processing}
        activeOpacity={0.85}
      >
        {processing ? (
          <ActivityIndicator color="#FFFFFF" />
        ) : (
          <Text style={styles.releaseButtonText}>Liberar al walker</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        style={[styles.refundButton, processing && styles.buttonDisabled]}
        onPress={confirmRefund}
        disabled={processing}
        activeOpacity={0.85}
      >
        <Text style={styles.refundButtonText}>Reembolsar al owner</Text>
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
    disputeBadge: {
      paddingHorizontal: spacing.sm,
      paddingVertical: 4,
      borderRadius: radius.sm,
      backgroundColor: "rgba(185,28,28,0.2)",
    },
    disputeBadgeText: { fontSize: 10, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
    amountBox: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.lg,
      marginBottom: spacing.md,
      alignItems: "center",
      borderWidth: 1,
      borderColor: colors.accent,
      ...shadows.card,
    },
    amountLabel: { fontSize: 11, fontWeight: "800", color: colors.textMuted, letterSpacing: 0.5 },
    amountValue: { fontSize: 32, fontWeight: "900", color: colors.accent, marginTop: spacing.xs },
    amountSplit: { flexDirection: "row", gap: spacing.md, marginTop: spacing.sm },
    amountSub: { fontSize: 11, color: colors.textMuted },
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
    rowValue: { fontSize: 13, fontWeight: "700", color: colors.text },
    reasonBox: {
      backgroundColor: "rgba(185,28,28,0.12)",
      borderRadius: radius.lg,
      padding: spacing.md,
      marginBottom: spacing.md,
      borderWidth: 1,
      borderColor: "#B91C1C",
    },
    reasonTitle: { fontSize: 11, fontWeight: "800", color: "#F87171", letterSpacing: 0.5 },
    reasonText: { fontSize: 14, color: colors.text, marginTop: spacing.xs, lineHeight: 20 },
    input: {
      backgroundColor: colors.background,
      borderRadius: radius.sm,
      padding: spacing.md,
      color: colors.text,
      fontSize: 14,
      minHeight: 70,
      textAlignVertical: "top",
      borderWidth: 1,
      borderColor: colors.border,
    },
    releaseButton: {
      backgroundColor: "#10B981",
      paddingVertical: spacing.md,
      borderRadius: radius.md,
      alignItems: "center",
      marginTop: spacing.sm,
      marginBottom: spacing.sm,
    },
    releaseButtonText: { color: "#FFFFFF", fontSize: 16, fontWeight: "800" },
    refundButton: {
      backgroundColor: "transparent",
      paddingVertical: spacing.md,
      borderRadius: radius.md,
      alignItems: "center",
      borderWidth: 1,
      borderColor: "#B91C1C",
    },
    refundButtonText: { color: "#F87171", fontSize: 16, fontWeight: "800" },
    buttonDisabled: { opacity: 0.6 },
  });
'''

path = os.path.join(MOBILE, "src", "screens", "AdminDisputeDetailScreen.tsx")
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(DETAIL_SCREEN)
print("[OK] screens/AdminDisputeDetailScreen.tsx")

# ==============================================================
# 4) Modificar App.tsx
# ==============================================================
APP_PATH = os.path.join(MOBILE, "App.tsx")
with open(APP_PATH, "rb") as f:
    src = f.read()

if b"AdminDisputesScreen" in src:
    print("[SKIP] App.tsx ya tiene AdminDisputesScreen")
else:
    viejo = b'import { WalkVerificationScreen } from "./src/screens/WalkVerificationScreen";'
    nuevo = (
        viejo + b'\n'
        b'import { AdminDisputesScreen } from "./src/screens/AdminDisputesScreen";\n'
        b'import { AdminDisputeDetailScreen } from "./src/screens/AdminDisputeDetailScreen";'
    )
    if viejo not in src:
        print("[FAIL] no encontre import de WalkVerificationScreen")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    viejo2 = b'<Stack.Screen name="WalkVerification" component={WalkVerificationScreen} options={{ title: "Verificacion" }} />'
    nuevo2 = (
        viejo2 + b'\n'
        b'            <Stack.Screen name="AdminDisputes" component={AdminDisputesScreen} options={{ title: "Disputas de pago" }} />\n'
        b'            <Stack.Screen name="AdminDisputeDetail" component={AdminDisputeDetailScreen} options={{ title: "Resolver disputa" }} />'
    )
    if viejo2 not in src:
        print("[FAIL] no encontre Stack.Screen de WalkVerification")
        sys.exit(1)
    src = src.replace(viejo2, nuevo2, 1)

    with open(APP_PATH, "wb") as f:
        f.write(src)
    print("[OK] App.tsx actualizado")

# ==============================================================
# 5) Modificar AdminHomeScreen
# ==============================================================
ADMIN_HOME = os.path.join(MOBILE, "src", "screens", "AdminHomeScreen.tsx")
with open(ADMIN_HOME, "rb") as f:
    src = f.read()

if b"AdminDisputes" in src:
    print("[SKIP] AdminHome ya tiene boton Disputas")
else:
    viejo = b'        <TouchableOpacity\n          style={styles.actionCard}\n          onPress={() => navigation.navigate("FlaggedWalks")}'
    # usamos str y encode para el bloque con emoji
    nuevo_str = '''        <TouchableOpacity
          style={[styles.actionCard, { borderColor: "#B91C1C" }]}
          onPress={() => navigation.navigate("AdminDisputes")}
          activeOpacity={0.9}
        >
          <View style={styles.actionIconWrap}>
            <Text style={styles.actionEmoji}>{"\\u26A0\\uFE0F"}</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={styles.actionTitle}>Disputas de pago</Text>
            <Text style={styles.actionSubtitle}>Resolver pagos en disputa</Text>
          </View>
          <Text style={styles.actionArrow}>{"\\u203A"}</Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.actionCard}
          onPress={() => navigation.navigate("FlaggedWalks")}'''
    nuevo = nuevo_str.encode("utf-8")

    if viejo not in src:
        print("[FAIL] no encontre FlaggedWalks en AdminHome")
        sys.exit(1)
    src = src.replace(viejo, nuevo, 1)

    with open(ADMIN_HOME, "wb") as f:
        f.write(src)
    print("[OK] Boton Disputas agregado a AdminHome")

print("\n[DONE] Panel de disputas creado!")