import os
from dotenv import load_dotenv

load_dotenv()

# Configuración de la API
API_KEY = os.getenv("API_KEY", "aabd5bd51a0557c33255327005fdbde372fb3c0e18b63906e29da5db07b62953")
API_SECRET = os.getenv("API_SECRET", "6f7e966d1ffddbbc2ded9f997bae330e50056ad2c80ec6b584c3f48a333e2486")
TESTNET = True

# Configuración de trading
CONFIG_TRADING = {
    'monto_operacion': 50.0,  # USDT (valor fijo)
    'apalancamiento': 20,
    'max_operaciones_simultaneas': 1,
    'activo': 'BTCUSDT',
    'tipo_margen': 'ISOLATED',
    'temporalidad_operaciones': '1m',  # 1 minuto
    'temporalidad_macd': '1h',  # 1 hora
    'macd_fast': 12,
    'macd_slow': 26,
    'macd_signal': 9,
    'take_profit_tipo': 'atr',  # 'atr' o 'porcentaje'
    'take_profit_valor': 2.0,  # Multiplicador ATR o porcentaje
    'stop_loss_tipo': 'porcentaje',  # 'porcentaje' o 'rr_ratio'
    'stop_loss_valor': 1.0,  # Porcentaje o relación riesgo/beneficio
    'stop_loss_habilitado': True,
    'comision': 0.0004,  # 0.04% de Binance
    'atr_periodo': 14
}

# Configuración de archivos
ARCHIVO_OPERACIONES = 'operaciones.csv'