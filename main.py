from flask import Flask, jsonify, render_template_string
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

# HTML template con botones
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot de Trading Binance</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f5f5f5; 
        }
        .container { 
            background: white; 
            padding: 30px; 
            border-radius: 10px; 
            box-shadow: 0 2px 10px rgba(0,0,0,0.1); 
        }
        h1 { 
            color: #2c3e50; 
            text-align: center; 
            margin-bottom: 30px; 
        }
        .status { 
            padding: 15px; 
            border-radius: 5px; 
            margin-bottom: 20px; 
            text-align: center;
            font-weight: bold;
        }
        .online { background-color: #d4edda; color: #155724; }
        .offline { background-color: #f8d7da; color: #721c24; }
        .error { background-color: #fff3cd; color: #856404; }
        .btn { 
            padding: 12px 20px; 
            margin: 5px; 
            border: none; 
            border-radius: 5px; 
            cursor: pointer; 
            font-size: 16px; 
            transition: all 0.3s; 
        }
        .btn-start { background-color: #28a745; color: white; }
        .btn-stop { background-color: #dc3545; color: white; }
        .btn-status { background-color: #17a2b8; color: white; }
        .btn-balance { background-color: #6c757d; color: white; }
        .btn-operaciones { background-color: #ffc107; color: black; }
        .btn:hover { opacity: 0.8; }
        .btn-container { 
            display: flex; 
            flex-wrap: wrap; 
            justify-content: center; 
            margin: 20px 0; 
        }
        .info-box { 
            background-color: #e9ecef; 
            padding: 15px; 
            border-radius: 5px; 
            margin: 10px 0; 
        }
        #result { 
            margin-top: 20px; 
            padding: 15px; 
            border-radius: 5px; 
            background-color: #f8f9fa; 
            display: none; 
        }
        .loading { 
            text-align: center; 
            color: #6c757d; 
            margin: 10px 0; 
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Bot de Trading Binance</h1>
        
        <div class="status" id="statusBox">
            {% if bot_running %}✅ Bot funcionando{% else %}❌ Bot detenido{% endif %}
        </div>

        <div class="btn-container">
            <button class="btn btn-start" onclick="controlBot('start')">▶️ Iniciar Bot</button>
            <button class="btn btn-stop" onclick="controlBot('stop')">⏹️ Detener Bot</button>
            <button class="btn btn-status" onclick="getStatus()">📊 Estado</button>
            <button class="btn btn-balance" onclick="getBalance()">💰 Balance</button>
            <button class="btn btn-operaciones" onclick="getOperaciones()">📈 Operaciones</button>
        </div>

        <div id="result"></div>
        <div id="loading" class="loading" style="display: none;">Cargando...</div>

        <div class="info-box">
            <h3>📋 Endpoints API:</h3>
            <ul>
                <li><code>GET /</code> - Esta interfaz</li>
                <li><code>GET /status</code> - Estado del bot</li>
                <li><code>GET /start</code> - Iniciar bot</li>
                <li><code>GET /stop</code> - Detener bot</li>
                <li><code>GET /balance</code> - Balance de cuenta</li>
                <li><code>GET /operaciones</code> - Operaciones</li>
            </ul>
        </div>
    </div>

    <script>
        function controlBot(action) {
            showLoading(true);
            fetch('/' + action)
                .then(response => response.json())
                .then(data => {
                    showResult(JSON.stringify(data, null, 2));
                    updateStatus();
                    showLoading(false);
                })
                .catch(error => {
                    showResult('Error: ' + error);
                    showLoading(false);
                });
        }

        function getStatus() {
            showLoading(true);
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    showResult(JSON.stringify(data, null, 2));
                    showLoading(false);
                })
                .catch(error => {
                    showResult('Error: ' + error);
                    showLoading(false);
                });
        }

        function getBalance() {
            showLoading(true);
            fetch('/balance')
                .then(response => response.json())
                .then(data => {
                    showResult(JSON.stringify(data, null, 2));
                    showLoading(false);
                })
                .catch(error => {
                    showResult('Error: ' + error);
                    showLoading(false);
                });
        }

        function getOperaciones() {
            showLoading(true);
            fetch('/operaciones')
                .then(response => response.json())
                .then(data => {
                    showResult(JSON.stringify(data, null, 2));
                    showLoading(false);
                })
                .catch(error => {
                    showResult('Error: ' + error);
                    showLoading(false);
                });
        }

        function updateStatus() {
            fetch('/status')
                .then(response => response.json())
                .then(data => {
                    const statusBox = document.getElementById('statusBox');
                    if (data.bot_running) {
                        statusBox.innerHTML = '✅ Bot funcionando';
                        statusBox.className = 'status online';
                    } else {
                        statusBox.innerHTML = '❌ Bot detenido';
                        statusBox.className = 'status offline';
                    }
                });
        }

        function showResult(content) {
            const resultDiv = document.getElementById('result');
            resultDiv.innerHTML = '<pre>' + content + '</pre>';
            resultDiv.style.display = 'block';
        }

        function showLoading(show) {
            document.getElementById('loading').style.display = show ? 'block' : 'none';
        }

        // Actualizar estado cada 10 segundos
        setInterval(updateStatus, 10000);
    </script>
</body>
</html>
"""

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
    """Página principal con interfaz web"""
    return render_template_string(HTML_TEMPLATE, bot_running=bot_state['running'])

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
    print("🌐 Interfaz web disponible en: http://localhost:5000")
    print("📋 Endpoints disponibles:")
    print("  - GET / → Interfaz web con botones")
    print("  - GET /status → Estado del bot y conexiones")
    print("  - GET /start → Iniciar bot")
    print("  - GET /stop → Detener bot")
    print("  - GET /balance → Ver balance")
    print("  - GET /operaciones → Ver operaciones")
    
    # Iniciar el servidor Flask
    app.run(host='0.0.0.0', port=10000, debug=False)