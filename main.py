from flask import Flask, jsonify
import threading
import time
import asyncio
from api_connection import APIConnection
from estrategia import EstrategiaMACD
from ejecucion import GestorOperaciones
from config import CONFIG_TRADING

app = Flask(__name__)

# Estado global del bot
bot_state = {
    'running': False,
    'bot_instance': None,
    'last_error': None,
    'start_time': None
}

class TradingBot:
    def __init__(self):
        self.api = APIConnection()
        self.estrategia = EstrategiaMACD()
        self.gestor = GestorOperaciones(self.api, self.estrategia)
        self.config = CONFIG_TRADING
        self.ultimo_tiempo_macd = 0
        self.running = False
        
    async def run(self):
        """Ejecutar el bot de trading"""
        print("Inicializando bot de trading...")
        
        # Configurar cuenta
        self.gestor.configurar_cuenta()
        
        # Suscribir a streams de WebSocket
        symbol_lower = self.config['activo'].lower()
        streams = [
            f"{symbol_lower}@kline_{self.config['temporalidad_operaciones']}",
            f"{symbol_lower}@kline_{self.config['temporalidad_macd']}"
        ]
        
        # Registrar callbacks
        self.api.register_callback(f"{symbol_lower}@kline_{self.config['temporalidad_operaciones']}", self.procesar_kline_1m)
        self.api.register_callback(f"{symbol_lower}@kline_{self.config['temporalidad_macd']}", self.procesar_kline_macd)
        
        # Iniciar conexión WebSocket en un hilo separado
        websocket_thread = threading.Thread(target=self.run_websocket, args=(streams,))
        websocket_thread.daemon = True
        websocket_thread.start()
        
        print("Bot inicializado y escuchando mercados...")
        self.running = True
        
        # Mantener el bot ejecutándose
        while self.running:
            await asyncio.sleep(1)
    
    def run_websocket(self, streams):
        """Ejecutar WebSocket en un hilo separado"""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.api.connect_websocket(streams))
    
    def procesar_kline_1m(self, data):
        """Procesar datos de kline de 1 minuto"""
        if data['e'] != 'kline':
            return
            
        kline = data['k']
        if not kline['x']:  # Si la vela no está cerrada, ignorar
            return
            
        timestamp = kline['t']
        open_price = float(kline['o'])
        high_price = float(kline['h'])
        low_price = float(kline['l'])
        close_price = float(kline['c'])
        volume = float(kline['v'])
        
        # Agregar datos a la estrategia
        self.estrategia.agregar_dato_ohlcv(
            timestamp, open_price, high_price, low_price, close_price, volume,
            self.config['temporalidad_operaciones']
        )
        
        # Verificar cierre de operaciones con el precio actual
        self.gestor.verificar_cierre_operaciones(close_price)
        
        # Generar y ejecutar señales (solo cada cierto tiempo para MACD)
        current_time = time.time()
        if current_time - self.ultimo_tiempo_macd >= 60:  # Cada minuto verificar MACD
            senal = self.estrategia.generar_senal()
            if senal:
                print(f"Señal generada: {senal.tipo} a {senal.precio}")
                self.gestor.abrir_operacion(senal)
            self.ultimo_tiempo_macd = current_time
    
    def procesar_kline_macd(self, data):
        """Procesar datos de kline para el timeframe del MACD"""
        if data['e'] != 'kline':
            return
            
        kline = data['k']
        if not kline['x']:  # Si la vela no está cerrada, ignorar
            return
            
        timestamp = kline['t']
        open_price = float(kline['o'])
        high_price = float(kline['h'])
        low_price = float(kline['l'])
        close_price = float(kline['c'])
        volume = float(kline['v'])
        
        # Agregar datos a la estrategia
        self.estrategia.agregar_dato_ohlcv(
            timestamp, open_price, high_price, low_price, close_price, volume,
            self.config['temporalidad_macd']
        )
    
    def stop(self):
        """Detener el bot"""
        self.running = False
        print("Bot detenido")
    
    def get_status(self):
        """Obtener estado del bot"""
        return {
            'running': self.running,
            'operaciones_activas': len(self.gestor.operaciones_activas),
            'operaciones_cerradas': len(self.gestor.operaciones_cerradas)
        }

def run_bot():
    """Función para ejecutar el bot en un hilo separado"""
    try:
        bot = TradingBot()
        bot_state['bot_instance'] = bot
        bot_state['last_error'] = None
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(bot.run())
        
    except Exception as e:
        bot_state['last_error'] = str(e)
        print(f"Error en el bot: {e}")

# Endpoints de la API
@app.route('/')
def home():
    return "Bot funcionando ✅"

@app.route('/status')
def status():
    """Endpoint de estado del bot"""
    try:
        # Verificar conexión a Binance
        api = APIConnection()
        balance_info = api.get_account_info()
        
        # Obtener balance de USDT
        usdt_balance = 0
        if balance_info:
            for asset in balance_info['assets']:
                if asset['asset'] == 'USDT':
                    usdt_balance = float(asset['availableBalance'])
                    break
        
        status_info = {
            'status': 'online',
            'bot_running': bot_state['running'],
            'binance_connected': balance_info is not None,
            'usdt_balance': usdt_balance,
            'operaciones_activas': 0,
            'operaciones_cerradas': 0,
            'uptime': None,
            'last_error': bot_state['last_error']
        }
        
        # Agregar información del bot si está corriendo
        if bot_state['bot_instance']:
            bot_status = bot_state['bot_instance'].get_status()
            status_info.update(bot_status)
        
        # Calcular uptime
        if bot_state['start_time']:
            status_info['uptime'] = time.time() - bot_state['start_time']
        
        return jsonify(status_info)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/start')
def start_bot():
    """Iniciar el bot"""
    if bot_state['running']:
        return jsonify({'status': 'already_running', 'message': 'El bot ya está en ejecución'})
    
    try:
        # Iniciar el bot en un hilo separado
        bot_thread = threading.Thread(target=run_bot)
        bot_thread.daemon = True
        bot_thread.start()
        
        bot_state['running'] = True
        bot_state['start_time'] = time.time()
        bot_state['last_error'] = None
        
        return jsonify({'status': 'started', 'message': 'Bot iniciado correctamente'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/stop')
def stop_bot():
    """Detener el bot"""
    if not bot_state['running'] or not bot_state['bot_instance']:
        return jsonify({'status': 'not_running', 'message': 'El bot no está en ejecución'})
    
    try:
        bot_state['bot_instance'].stop()
        bot_state['running'] = False
        return jsonify({'status': 'stopped', 'message': 'Bot detenido correctamente'})
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/balance')
def get_balance():
    """Obtener balance de la cuenta"""
    try:
        api = APIConnection()
        balance_info = api.get_account_info()
        
        if not balance_info:
            return jsonify({'status': 'error', 'message': 'No se pudo obtener información de la cuenta'}), 500
        
        # Filtrar solo los balances relevantes
        balances = []
        for asset in balance_info['assets']:
            if float(asset['walletBalance']) > 0:
                balances.append({
                    'asset': asset['asset'],
                    'balance': float(asset['walletBalance']),
                    'available': float(asset['availableBalance'])
                })
        
        return jsonify({
            'status': 'success',
            'balances': balances
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/operaciones')
def get_operaciones():
    """Obtener información de las operaciones"""
    try:
        if not bot_state['bot_instance']:
            return jsonify({'status': 'error', 'message': 'Bot no inicializado'}), 400
        
        operaciones = {
            'activas': bot_state['bot_instance'].gestor.operaciones_activas,
            'cerradas': bot_state['bot_instance'].gestor.operaciones_cerradas
        }
        
        return jsonify({
            'status': 'success',
            'operaciones': operaciones
        })
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == "__main__":
    print("Iniciando servidor web del bot de trading...")
    print("Endpoints disponibles:")
    print("  - GET / → Estado del servidor")
    print("  - GET /status → Estado del bot y conexiones")
    print("  - GET /start → Iniciar bot")
    print("  - GET /stop → Detener bot")
    print("  - GET /balance → Ver balance")
    print("  - GET /operaciones → Ver operaciones")
    
    # Iniciar el servidor Flask
    app.run(host='0.0.0.0', port=5000, debug=False)