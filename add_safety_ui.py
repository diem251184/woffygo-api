import os, sys, shutil

MOBILE = r"C:\woffy-mobile"

# ============================================================
# 1) Crear service safetyReports.ts
# ============================================================
SERVICE_PATH = os.path.join(MOBILE, "src", "services", "safetyReports.ts")

SERVICE_CONTENT = '''import api from "./api";

export type SafetyCategory = "danger" | "low_visibility" | "other";

export interface SafetyReport {
  id: number;
  category: SafetyCategory;
  description: string | null;
  latitude: number;
  longitude: number;
  verified: boolean;
  created_at: string;
  expires_at: string;
  reporter_id: number;
  reporter_name: string;
  reporter_role: string;
  walk_id: number | null;
}

export interface SafetyReportAdmin extends SafetyReport {
  deleted: boolean;
  deleted_reason: string | null;
}

export interface CreateReportPayload {
  category: SafetyCategory;
  description?: string | null;
  latitude: number;
  longitude: number;
  walk_id?: number | null;
}

export const CATEGORY_LABELS: Record<SafetyCategory, string> = {
  danger: "Peligro",
  low_visibility: "Poca visibilidad",
  other: "Otro",
};

export const CATEGORY_EMOJIS: Record<SafetyCategory, string> = {
  danger: "\\u26A0\\uFE0F",
  low_visibility: "\\u{1F311}",
  other: "\\u2753",
};

export const CATEGORY_COLORS: Record<SafetyCategory, string> = {
  danger: "#EF4444",
  low_visibility: "#6366F1",
  other: "#9CA3AF",
};

export async function createSafetyReport(payload: CreateReportPayload): Promise<SafetyReport> {
  const res = await api.post<SafetyReport>("/safety-reports", payload);
  return res.data;
}

export async function getNearbySafetyReports(
  lat: number,
  lng: number,
  radiusKm: number = 10
): Promise<SafetyReport[]> {
  const res = await api.get<SafetyReport[]>(
    `/safety-reports/nearby?lat=${lat}&lng=${lng}&radius_km=${radiusKm}`
  );
  return res.data;
}

// ============ ADMIN ============

export async function getAdminSafetyReports(includeDeleted = false): Promise<SafetyReportAdmin[]> {
  const res = await api.get<SafetyReportAdmin[]>(
    `/admin/safety-reports?include_deleted=${includeDeleted}`
  );
  return res.data;
}

export async function verifySafetyReport(reportId: number): Promise<SafetyReportAdmin> {
  const res = await api.post<SafetyReportAdmin>(`/admin/safety-reports/${reportId}/verify`, {});
  return res.data;
}

export async function deleteSafetyReport(reportId: number, reason?: string): Promise<void> {
  await api.delete(`/admin/safety-reports/${reportId}`, {
    data: { reason: reason || null },
  });
}
'''

with open(SERVICE_PATH, "w", encoding="utf-8", newline="\n") as f:
    f.write(SERVICE_CONTENT)
print("[OK] services/safetyReports.ts")

# ============================================================
# 2) Modificar WalkDetailScreen:
#    - Importar service + useLocation
#    - Agregar estado + handler + modal
#    - Boton "Reportar zona" si status en proceso/aceptado
# ============================================================
WD_PATH = os.path.join(MOBILE, "src", "screens", "WalkDetailScreen.tsx")

backup = WD_PATH + ".safetyreport.bak"
if not os.path.exists(backup):
    shutil.copyfile(WD_PATH, backup)
    print("[BACKUP] " + backup)

with open(WD_PATH, "r", encoding="utf-8") as f:
    src = f.read()

if "createSafetyReport" in src:
    print("[SKIP] WalkDetailScreen ya tiene reporte de seguridad")
else:
    # 2a) Agregar imports
    viejo_imp = 'import { createReview, getReviewByWalk, Review } from "../services/reviews";'
    nuevo_imp = (
        viejo_imp + "\n"
        'import { createSafetyReport, SafetyCategory } from "../services/safetyReports";\n'
        'import { useLocation } from "../hooks/useLocation";'
    )
    if viejo_imp not in src:
        print("[FAIL] no encontre import de reviews")
        sys.exit(1)
    src = src.replace(viejo_imp, nuevo_imp, 1)

    # 2b) Agregar state hooks despues de existingReview
    viejo_state = '  const [existingReview, setExistingReview] = useState<Review | null>(null);'
    nuevo_state = (
        viejo_state + "\n"
        '  const [safetyModalVisible, setSafetyModalVisible] = useState(false);\n'
        '  const [safetyCategory, setSafetyCategory] = useState<SafetyCategory | null>(null);\n'
        '  const [safetyDescription, setSafetyDescription] = useState("");\n'
        '  const [safetySaving, setSafetySaving] = useState(false);\n'
        '  const { coords: safetyCoords, refresh: refreshSafetyCoords } = useLocation(false);'
    )
    if viejo_state not in src:
        print("[FAIL] no encontre existingReview state")
        sys.exit(1)
    src = src.replace(viejo_state, nuevo_state, 1)

    # 2c) Agregar handler antes del return, buscando "if (loading || !walk)"
    viejo_handler = '  if (loading || !walk) {'
    nuevo_handler = '''  async function handleReportSafety() {
    if (!safetyCategory) {
      Alert.alert("Falta categoria", "Elegi un tipo de reporte");
      return;
    }
    if (!walk) return;

    setSafetySaving(true);
    try {
      // Asegurar coords
      let lat = safetyCoords?.latitude;
      let lng = safetyCoords?.longitude;
      if (!lat || !lng) {
        await refreshSafetyCoords();
        lat = safetyCoords?.latitude;
        lng = safetyCoords?.longitude;
      }
      if (!lat || !lng) {
        Alert.alert("Sin ubicacion", "No pudimos obtener tu ubicacion. Activa el GPS.");
        setSafetySaving(false);
        return;
      }

      await createSafetyReport({
        category: safetyCategory,
        description: safetyDescription.trim() || null,
        latitude: lat,
        longitude: lng,
        walk_id: walk.id,
      });

      setSafetyModalVisible(false);
      setSafetyCategory(null);
      setSafetyDescription("");
      Alert.alert("Reporte enviado", "Gracias, tu reporte ya esta visible en el mapa");
    } catch (e: any) {
      Alert.alert("Error", e?.response?.data?.detail || "No se pudo enviar el reporte");
    } finally {
      setSafetySaving(false);
    }
  }

  if (loading || !walk) {'''
    if viejo_handler not in src:
        print("[FAIL] no encontre 'if (loading || !walk)'")
        sys.exit(1)
    src = src.replace(viejo_handler, nuevo_handler, 1)

    # 2d) Agregar el boton "Reportar zona" en el JSX
    # Lo ponemos justo despues del bloque canChat (chatButton)
    viejo_jsx = '''        {canChat && (
          <TouchableOpacity
            style={styles.chatButton}'''
    nuevo_jsx = '''        {(walk.status === "aceptado" || walk.status === "en_proceso") && (
          <TouchableOpacity
            style={styles.safetyReportButton}
            onPress={() => setSafetyModalVisible(true)}
            activeOpacity={0.85}
          >
            <Text style={styles.safetyReportEmoji}>{"\\u26A0\\uFE0F"}</Text>
            <Text style={styles.safetyReportText}>Reportar zona</Text>
          </TouchableOpacity>
        )}

        {canChat && (
          <TouchableOpacity
            style={styles.chatButton}'''
    if viejo_jsx not in src:
        print("[WARN] no encontre bloque de chatButton, insertando de otra forma")
        # Buscar cualquier punto de referencia distinto
        viejo_jsx = "        {canChat && ("
        nuevo_jsx = '''        {(walk.status === "aceptado" || walk.status === "en_proceso") && (
          <TouchableOpacity
            style={styles.safetyReportButton}
            onPress={() => setSafetyModalVisible(true)}
            activeOpacity={0.85}
          >
            <Text style={styles.safetyReportEmoji}>{"\\u26A0\\uFE0F"}</Text>
            <Text style={styles.safetyReportText}>Reportar zona</Text>
          </TouchableOpacity>
        )}

        {canChat && ('''
        if viejo_jsx in src:
            src = src.replace(viejo_jsx, nuevo_jsx, 1)
        else:
            print("[FAIL] no encontre donde insertar el boton")
            sys.exit(1)
    else:
        src = src.replace(viejo_jsx, nuevo_jsx, 1)
    print("[OK] Boton Reportar zona insertado")

    # 2e) Agregar el Modal al final (antes del ultimo </View>)
    viejo_modal = '''      </Modal>
    </View>
  );
}'''
    nuevo_modal = '''      </Modal>

      <Modal
        visible={safetyModalVisible}
        animationType="slide"
        transparent
        onRequestClose={() => {
          if (!safetySaving) {
            setSafetyModalVisible(false);
            setSafetyCategory(null);
            setSafetyDescription("");
          }
        }}
      >
        <KeyboardAvoidingView
          style={styles.modalOverlay}
          behavior={Platform.OS === "ios" ? "padding" : undefined}
        >
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>Reportar zona</Text>
            <Text style={styles.modalHint}>
              Va a quedar visible en el mapa para otros usuarios por 30 dias. La otra parte va a ver tu nombre.
            </Text>

            <View style={{ flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
              {([
                { key: "danger", label: "Peligro", emoji: "\\u26A0\\uFE0F" },
                { key: "low_visibility", label: "Poca visibilidad", emoji: "\\u{1F311}" },
                { key: "other", label: "Otro", emoji: "\\u2753" },
              ] as { key: SafetyCategory; label: string; emoji: string }[]).map((c) => {
                const selected = safetyCategory === c.key;
                return (
                  <TouchableOpacity
                    key={c.key}
                    onPress={() => setSafetyCategory(c.key)}
                    disabled={safetySaving}
                    activeOpacity={0.8}
                    style={{
                      paddingHorizontal: 14,
                      paddingVertical: 10,
                      borderRadius: 20,
                      borderWidth: 1,
                      borderColor: selected ? colors.primary : colors.border,
                      backgroundColor: selected ? colors.primary : "transparent",
                    }}
                  >
                    <Text style={{ color: selected ? "#FFFFFF" : colors.text, fontSize: 13, fontWeight: "700" }}>
                      {c.emoji}  {c.label}
                    </Text>
                  </TouchableOpacity>
                );
              })}
            </View>

            <TextInput
              style={[styles.input, styles.inputMultiline]}
              value={safetyDescription}
              onChangeText={setSafetyDescription}
              placeholder="Contanos mas (opcional)"
              placeholderTextColor={colors.textMuted}
              multiline
              numberOfLines={3}
              editable={!safetySaving}
              maxLength={500}
            />

            <TouchableOpacity
              style={[styles.cancelWalkConfirmButton, (safetySaving || !safetyCategory) && styles.buttonDisabled]}
              onPress={handleReportSafety}
              disabled={safetySaving || !safetyCategory}
              activeOpacity={0.85}
            >
              {safetySaving ? (
                <ActivityIndicator color="#FFFFFF" />
              ) : (
                <Text style={styles.cancelWalkConfirmText}>Enviar reporte</Text>
              )}
            </TouchableOpacity>

            <TouchableOpacity
              style={styles.cancelButton}
              onPress={() => {
                if (safetySaving) return;
                setSafetyModalVisible(false);
                setSafetyCategory(null);
                setSafetyDescription("");
              }}
              disabled={safetySaving}
            >
              <Text style={styles.cancelButtonText}>Volver</Text>
            </TouchableOpacity>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}'''
    if viejo_modal not in src:
        print("[FAIL] no encontre el cierre del ultimo Modal")
        sys.exit(1)
    src = src.replace(viejo_modal, nuevo_modal, 1)
    print("[OK] Modal de reporte insertado")

    # 2f) Agregar estilos (antes de cancelBanner)
    viejo_style = "    cancelBanner: {"
    nuevo_style = '''    safetyReportButton: {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      backgroundColor: "rgba(239,68,68,0.12)",
      borderWidth: 1,
      borderColor: "#EF4444",
      borderRadius: radius.md,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.lg,
      marginBottom: spacing.md,
      gap: 10,
    },
    safetyReportEmoji: { fontSize: 20 },
    safetyReportText: { fontSize: 15, fontWeight: "800", color: "#F87171", letterSpacing: 0.3 },
    cancelBanner: {'''
    if viejo_style not in src:
        print("[WARN] no encontre cancelBanner en estilos")
    else:
        src = src.replace(viejo_style, nuevo_style, 1)
        print("[OK] Estilos agregados")

    with open(WD_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(src)

print("[DONE] WalkDetailScreen actualizado")