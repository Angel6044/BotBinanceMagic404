import asyncio
import json
import time
from api_connection import APIConnection
from estrategia import EstrategiaMACD
from ejecucion import GestorOperaciones
from config import CONFIG_TRADING

class BotTrading:
    def __init__(self):
        self.api = APIConnection()
        self.estrategia = EstrategiaMACD()
        self.gestor = GestorOperaciones(self.api, self.estrategia)
        self.config = CONFIG_TRADING
        self.ultimo_tiempo_macd = 0
        
    async def inicializar(self):
        """Inicializar el bot"""
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
        
        # Iniciar conexión WebSocket
        asyncio.create_task(self.api.connect_websocket(streams))
        
        print("Bot inicializado y escuchando mercados...")
    
    def procesar_kline_1m(self, data):
        """Procesar datos de kline de 1 minuto"""
        if data['e'] != 'kline':
            return
            
        kline = data['k']
        print(f"Vela 1m - Cerrada: {kline['x']}, Precio: {kline['c']}")
        
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
        print(f"Vela MACD recibida - Timeframe: {kline['i']}, Cerrada: {kline['x']}")

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

async def main():
    bot = BotTrading()
    await bot.inicializar()
    
    # Mantener el bot ejecutándose
    while True:
        await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario")
    except Exception as e:
        print(f"Error inesperado: {e}")