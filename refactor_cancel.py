import io, os, shutil, sys, re

MOBILE = r"C:\woffy-mobile"
COMPONENT_PATH = os.path.join(MOBILE, "src", "components", "CancelWalkModal.tsx")
MYWALKS_PATH = os.path.join(MOBILE, "src", "screens", "MyWalksScreen.tsx")

COMPONENT_CONTENT = b'''import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  TextInput,
  Modal,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  StyleSheet,
} from "react-native";
import { useTheme } from "../contexts/ThemeContext";
import { spacing, radius } from "../theme/colors";

export const CANCEL_MOTIVOS = [
  { key: "no_puedo_llegar", label: "No puedo llegar", text: "No puedo llegar al punto de encuentro" },
  { key: "emergencia", label: "Emergencia personal", text: "Tuve una emergencia personal" },
  { key: "mascota_agresiva", label: "Mascota agresiva", text: "La mascota mostro comportamiento agresivo" },
  { key: "problema_pago", label: "Problema de pago", text: "Hubo un problema con el pago del paseo" },
  { key: "otro", label: "Otro (escribir)", text: "" },
];

type Props = {
  visible: boolean;
  walkId: number | null;
  processing: boolean;
  onClose: () => void;
  onConfirm: (reason: string) => void;
};

export function CancelWalkModal({ visible, walkId, processing, onClose, onConfirm }: Props) {
  const { colors } = useTheme();
  const styles = makeStyles(colors);
  const [motivoKey, setMotivoKey] = useState<string>("");
  const [otroTexto, setOtroTexto] = useState<string>("");

  function reset() {
    setMotivoKey("");
    setOtroTexto("");
  }

  function handleClose() {
    if (processing) return;
    reset();
    onClose();
  }

  function handleConfirm() {
    const opt = CANCEL_MOTIVOS.find((m) => m.key === motivoKey);
    if (!opt) return;
    if (opt.key === "otro") {
      const t = otroTexto.trim();
      if (t.length < 5) return;
      onConfirm(t);
    } else {
      onConfirm(opt.text);
    }
  }

  const opt = CANCEL_MOTIVOS.find((m) => m.key === motivoKey);
  const motivoValido = !!opt && (opt.key !== "otro" || otroTexto.trim().length >= 5);

  return (
    <Modal
      visible={visible}
      animationType="slide"
      transparent
      onRequestClose={handleClose}
    >
      <KeyboardAvoidingView
        style={styles.modalOverlay}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.modalContent}>
          <Text style={styles.modalTitle}>Cancelar paseo</Text>
          <Text style={styles.modalHint}>
            Contanos por que cancelas este paseo{walkId ? " #" + walkId : ""}. La otra parte va a ver el motivo.
          </Text>

          <View style={styles.chipsWrap}>
            {CANCEL_MOTIVOS.map((m) => {
              const selected = motivoKey === m.key;
              return (
                <TouchableOpacity
                  key={m.key}
                  onPress={() => setMotivoKey(m.key)}
                  disabled={processing}
                  activeOpacity={0.8}
                  style={[
                    styles.chip,
                    {
                      borderColor: selected ? colors.primary : colors.border,
                      backgroundColor: selected ? colors.primary : "transparent",
                    },
                  ]}
                >
                  <Text style={[styles.chipText, { color: selected ? colors.white : colors.text }]}>
                    {m.label}
                  </Text>
                </TouchableOpacity>
              );
            })}
          </View>

          {motivoKey === "otro" && (
            <TextInput
              style={styles.input}
              value={otroTexto}
              onChangeText={setOtroTexto}
              placeholder="Escribi el motivo (minimo 5 caracteres)"
              placeholderTextColor={colors.textMuted}
              multiline
              numberOfLines={3}
              editable={!processing}
              autoFocus
              maxLength={300}
            />
          )}

          {motivoKey === "otro" && otroTexto.trim().length > 0 && otroTexto.trim().length < 5 && (
            <Text style={styles.errorText}>Escribi al menos 5 caracteres</Text>
          )}

          <TouchableOpacity
            style={[styles.confirmButton, (!motivoValido || processing) && styles.buttonDisabled]}
            onPress={handleConfirm}
            disabled={!motivoValido || processing}
            activeOpacity={0.85}
          >
            {processing ? (
              <ActivityIndicator color={colors.white} />
            ) : (
              <Text style={styles.confirmText}>Confirmar cancelacion</Text>
            )}
          </TouchableOpacity>

          <TouchableOpacity
            style={styles.cancelBtn}
            onPress={handleClose}
            disabled={processing}
          >
            <Text style={styles.cancelBtnText}>Volver</Text>
          </TouchableOpacity>
        </View>
      </KeyboardAvoidingView>
    </Modal>
  );
}

const makeStyles = (colors: any) =>
  StyleSheet.create({
    modalOverlay: {
      flex: 1,
      backgroundColor: "rgba(0,0,0,0.55)",
      justifyContent: "center",
      padding: spacing.md,
    },
    modalContent: {
      backgroundColor: colors.surface,
      borderRadius: radius.lg,
      padding: spacing.lg,
      borderWidth: 1,
      borderColor: colors.border,
    },
    modalTitle: {
      fontSize: 20,
      fontWeight: "800",
      color: colors.text,
      marginBottom: spacing.xs,
    },
    modalHint: {
      fontSize: 13,
      color: colors.textMuted,
      marginBottom: spacing.md,
      lineHeight: 18,
    },
    chipsWrap: {
      flexDirection: "row",
      flexWrap: "wrap",
      gap: 8,
      marginBottom: spacing.md,
    },
    chip: {
      paddingHorizontal: 12,
      paddingVertical: 8,
      borderRadius: 20,
      borderWidth: 1,
    },
    chipText: {
      fontSize: 13,
      fontWeight: "600",
    },
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
      marginBottom: spacing.sm,
    },
    errorText: {
      color: "#F87171",
      fontSize: 12,
      marginBottom: spacing.sm,
    },
    confirmButton: {
      backgroundColor: "#B91C1C",
      paddingVertical: spacing.md,
      borderRadius: radius.sm,
      alignItems: "center",
      marginTop: spacing.xs,
    },
    confirmText: {
      color: "#FFFFFF",
      fontWeight: "800",
      fontSize: 15,
    },
    buttonDisabled: {
      opacity: 0.6,
    },
    cancelBtn: {
      paddingVertical: spacing.md,
      alignItems: "center",
      marginTop: spacing.xs,
    },
    cancelBtnText: {
      color: colors.textMuted,
      fontWeight: "700",
      fontSize: 14,
    },
  });
'''

# 1) Crear carpeta components si no existe
os.makedirs(os.path.dirname(COMPONENT_PATH), exist_ok=True)

# 2) Escribir componente
with open(COMPONENT_PATH, "wb") as f:
    f.write(COMPONENT_CONTENT)
print("[OK] Componente creado: " + COMPONENT_PATH)

# 3) Backup de MyWalksScreen
backup = MYWALKS_PATH + ".bak"
if not os.path.exists(backup):
    shutil.copyfile(MYWALKS_PATH, backup)
    print("[BACKUP] " + backup)
else:
    print("[SKIP] backup ya existe")

# 4) Leer binario
with open(MYWALKS_PATH, "rb") as f:
    src = f.read()

nl = b"\r\n" if b"\r\n" in src[:5000] else b"\n"
orig = src

# --- A) Import ---
old_import = b'import { spacing, radius, shadows } from "../theme/colors";'
new_import = old_import + nl + b'import { CancelWalkModal } from "../components/CancelWalkModal";'
if old_import not in src:
    print("[FAIL] A - no encontre import")
    sys.exit(1)
src = src.replace(old_import, new_import, 1)
print("[OK] A - import agregado")

# --- B) Estado ---
old_state = b'  const [actingId, setActingId] = useState<number | null>(null);'
new_state = (
    old_state + nl +
    b'  const [cancelTarget, setCancelTarget] = useState<Walk | null>(null);' + nl +
    b'  const [cancelProcessing, setCancelProcessing] = useState(false);'
)
if old_state not in src:
    print("[FAIL] B - no encontre state")
    sys.exit(1)
src = src.replace(old_state, new_state, 1)
print("[OK] B - estados agregados")

# --- C) Reemplazo handleCancel + agrego handleCancelConfirm ---
pat_c = re.compile(
    rb'  async function handleCancel\(walk: Walk\) \{.*?\r?\n  \}\r?\n\r?\n  if \(loading\) \{',
    re.DOTALL
)
new_handler = (
    b'  function handleCancel(walk: Walk) {' + nl +
    b'    setCancelTarget(walk);' + nl +
    b'  }' + nl + nl +
    b'  async function handleCancelConfirm(reason: string) {' + nl +
    b'    if (!cancelTarget) return;' + nl +
    b'    setCancelProcessing(true);' + nl +
    b'    setActingId(cancelTarget.id);' + nl +
    b'    try {' + nl +
    b'      await cancelWalk(cancelTarget.id, reason);' + nl +
    b'      setCancelTarget(null);' + nl +
    b'      await load();' + nl +
    b'    } catch (err: any) {' + nl +
    b'      Alert.alert("Error", err?.response?.data?.detail || "No se pudo cancelar");' + nl +
    b'    } finally {' + nl +
    b'      setCancelProcessing(false);' + nl +
    b'      setActingId(null);' + nl +
    b'    }' + nl +
    b'  }' + nl + nl +
    b'  if (loading) {'
)
if not pat_c.search(src):
    print("[FAIL] C - no encontre handleCancel")
    sys.exit(1)
src = pat_c.sub(new_handler, src, count=1)
print("[OK] C - handler reemplazado")

# --- D) Modal al final del JSX ---
old_close = nl + b'    </View>' + nl + b'  );' + nl + b'}' + nl + nl + b'const makeStyles'
modal_jsx = (
    nl + nl +
    b'      <CancelWalkModal' + nl +
    b'        visible={cancelTarget !== null}' + nl +
    b'        walkId={cancelTarget ? cancelTarget.id : null}' + nl +
    b'        processing={cancelProcessing}' + nl +
    b'        onClose={() => { if (!cancelProcessing) setCancelTarget(null); }}' + nl +
    b'        onConfirm={handleCancelConfirm}' + nl +
    b'      />' + nl +
    b'    </View>' + nl + b'  );' + nl + b'}' + nl + nl + b'const makeStyles'
)
if old_close not in src:
    print("[FAIL] D - no encontre cierre del JSX")
    sys.exit(1)
src = src.replace(old_close, modal_jsx, 1)
print("[OK] D - modal agregado al JSX")

# 5) Escribir
if src == orig:
    print("[WARN] no hubo cambios")
    sys.exit(1)

with open(MYWALKS_PATH, "wb") as f:
    f.write(src)

print("[DONE] MyWalksScreen.tsx actualizado")