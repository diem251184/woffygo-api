import io, re, sys, shutil

path = r"C:\woffy-mobile\src\screens\WalkDetailScreen.tsx"
backup = path + ".bak"

shutil.copyfile(path, backup)
print("[BACKUP] " + backup)

with io.open(path, "r", encoding="utf-8", newline="") as f:
    src = f.read()

orig = src
nl = "\r\n" if "\r\n" in src[:5000] else "\n"

def rep_regex(pattern, replacement, label):
    global src
    new_src, n = re.subn(pattern, replacement, src, count=1)
    if n == 0:
        print("[FAIL] " + label)
        sys.exit(1)
    src = new_src
    print("[OK]   " + label)

# --- A: agregar estado cancelMotivoKey
rep_regex(
    r'  const \[cancelModalVisible, setCancelModalVisible\] = useState\(false\);\r?\n  const \[cancelReason, setCancelReason\] = useState\(""\);',
    (
        '  const [cancelModalVisible, setCancelModalVisible] = useState(false);' + nl +
        '  const [cancelMotivoKey, setCancelMotivoKey] = useState<string>("");' + nl +
        '  const [cancelReason, setCancelReason] = useState("");'
    ),
    "A - estado cancelMotivoKey"
)

# --- B: reemplazar handleCancelWalk (agrega CANCEL_MOTIVOS + logica)
new_handler = (
    '  const CANCEL_MOTIVOS = [' + nl +
    '    { key: "no_puedo_llegar", label: "No puedo llegar", text: "No puedo llegar al punto de encuentro" },' + nl +
    '    { key: "emergencia", label: "Emergencia personal", text: "Tuve una emergencia personal" },' + nl +
    '    { key: "mascota_agresiva", label: "Mascota agresiva", text: "La mascota mostro comportamiento agresivo" },' + nl +
    '    { key: "problema_pago", label: "Problema de pago", text: "Hubo un problema con el pago del paseo" },' + nl +
    '    { key: "otro", label: "Otro (escribir)", text: "" },' + nl +
    '  ];' + nl + nl +
    '  async function handleCancelWalk() {' + nl +
    '    const opt = CANCEL_MOTIVOS.find((m) => m.key === cancelMotivoKey);' + nl +
    '    if (!opt) {' + nl +
    '      Alert.alert("Elegi un motivo", "Tenes que elegir un motivo de la lista");' + nl +
    '      return;' + nl +
    '    }' + nl +
    '    const finalReason = opt.key === "otro" ? cancelReason.trim() : opt.text;' + nl +
    '    if (opt.key === "otro" && finalReason.length < 5) {' + nl +
    '      Alert.alert("Motivo muy corto", "Escribi al menos 5 caracteres explicando por que cancelas");' + nl +
    '      return;' + nl +
    '    }' + nl +
    '    setProcessing(true);' + nl +
    '    try {' + nl +
    '      const updated = await cancelWalk(walkId, finalReason);' + nl +
    '      setWalk(updated);' + nl +
    '      setCancelModalVisible(false);' + nl +
    '      setCancelMotivoKey("");' + nl +
    '      setCancelReason("");' + nl +
    '      Alert.alert("Paseo cancelado", "El paseo fue cancelado correctamente");' + nl +
    '    } catch (err: any) {' + nl +
    '      Alert.alert("Error", err?.response?.data?.detail || "No se pudo cancelar el paseo");' + nl +
    '    } finally {' + nl +
    '      setProcessing(false);' + nl +
    '    }' + nl +
    '  }' + nl + nl +
    '  function openCancelConfirm() {'
)

rep_regex(
    r'  async function handleCancelWalk\(\) \{[\s\S]*?\r?\n  \}\r?\n\r?\n  function openCancelConfirm\(\) \{',
    new_handler,
    "B - handleCancelWalk + CANCEL_MOTIVOS"
)

# --- C: modal con chips + input condicional
new_modal = (
    '            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>' + nl +
    '              {CANCEL_MOTIVOS.map((m) => {' + nl +
    '                const selected = cancelMotivoKey === m.key;' + nl +
    '                return (' + nl +
    '                  <TouchableOpacity' + nl +
    '                    key={m.key}' + nl +
    '                    onPress={() => setCancelMotivoKey(m.key)}' + nl +
    '                    disabled={processing}' + nl +
    '                    activeOpacity={0.8}' + nl +
    '                    style={{' + nl +
    '                      paddingHorizontal: 12,' + nl +
    '                      paddingVertical: 8,' + nl +
    '                      borderRadius: 20,' + nl +
    '                      borderWidth: 1,' + nl +
    '                      borderColor: selected ? colors.primary : "#666",' + nl +
    '                      backgroundColor: selected ? colors.primary : "transparent",' + nl +
    '                    }}' + nl +
    '                  >' + nl +
    '                    <Text style={{ color: selected ? "#FFFFFF" : colors.text, fontSize: 13 }}>' + nl +
    '                      {m.label}' + nl +
    '                    </Text>' + nl +
    '                  </TouchableOpacity>' + nl +
    '                );' + nl +
    '              })}' + nl +
    '            </View>' + nl +
    '            {cancelMotivoKey === "otro" && (' + nl +
    '              <TextInput' + nl +
    '                style={[styles.input, styles.inputMultiline]}' + nl +
    '                value={cancelReason}' + nl +
    '                onChangeText={setCancelReason}' + nl +
    '                placeholder="Escribi el motivo (minimo 5 caracteres)"' + nl +
    '                placeholderTextColor={colors.textMuted}' + nl +
    '                multiline' + nl +
    '                numberOfLines={3}' + nl +
    '                editable={!processing}' + nl +
    '                autoFocus' + nl +
    '                maxLength={300}' + nl +
    '              />' + nl +
    '            )}'
)

rep_regex(
    r'            <TextInput\r?\n              style=\{\[styles\.input, styles\.inputMultiline\]\}\r?\n              value=\{cancelReason\}\r?\n              onChangeText=\{setCancelReason\}\r?\n              placeholder="Ej: se me complico el horario"[\s\S]*?\r?\n            />',
    new_modal,
    "C - modal chips + input condicional"
)

if src == orig:
    print("[FAIL] No hubo cambios")
    sys.exit(1)

with io.open(path, "w", encoding="utf-8", newline="") as f:
    f.write(src)

print("[DONE] Archivo actualizado OK")