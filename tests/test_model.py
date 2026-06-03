# =============================================================================
# tests/test_model.py
# -----------------------------------------------------------------------------
# Pruebas unitarias que corre la etapa "test" del pipeline de GitHub Actions.
# El enunciado exige AL MENOS estas dos:
#
#   PRUEBA 1 (test_model_responde):
#     Verificar que el modelo responde con datos de entrada definidos.
#     -> Se le pasa un tensor (1,1,28,28) y se comprueba que la salida tiene
#        forma (1,10) y no contiene NaN.
#
#   PRUEBA 2 (test_metrica_no_degrada):
#     Verificar que no hay un cambio significativo en una metrica definida.
#     -> Se calcula el accuracy del modelo sobre el set de prueba descargado
#        del Blob, y se valida que sea >= un umbral (ej: 0.90). Si el nuevo
#        modelo degrada por debajo del umbral, la prueba falla y el pipeline
#        NO promueve el modelo a produccion. Esto es el "quality gate".
#
# Tanto el modelo .onnx como los datos de prueba se obtienen del Blob Storage
# ANTES de correr estas pruebas (los descarga un step previo del workflow).
# =============================================================================

# TODO: implementar en el siguiente paso del proyecto.
