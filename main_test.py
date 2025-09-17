import asyncio
import time
from api_connection import APIConnection
from estrategia import Signal, EstrategiaMACD
from ejecucion import GestorOperaciones
from config import CONFIG_TRADING

class TestBot:
    def __init__(self):
        self.api = APIConnection()
        self.estrategia = EstrategiaMACD()
        self.gestor = GestorOperaciones(self.api, self.estrategia)
        self.config = CONFIG_TRADING
        
    async def ejecutar_prueba(self):
        """Ejecutar una operación de prueba"""
        print("=== INICIANDO PRUEBA DE OPERACIÓN ===")
        
        # Configurar cuenta
        self.gestor.configurar_cuenta()
        
        # Obtener precio actual
        precio_actual = self.obtener_precio_actual()
        if not precio_actual:
            print("Error obteniendo precio actual")
            return False
        
        print(f"Precio actual de {self.config['activo']}: {precio_actual}")
        
        # Usar monto suficiente para evitar problemas de precisión
        self.config['monto_operacion'] = 200  # USDT
        
        # Crear señal de prueba
        senal_prueba = Signal(
            tipo='long',
            precio=precio_actual,
            timestamp=int(time.time() * 1000),
            atr=100
        )
        
        # Forzar configuración de TP/SL al 1%
        self.estrategia.config['take_profit_tipo'] = 'porcentaje'
        self.estrategia.config['take_profit_valor'] = 1.0
        self.estrategia.config['stop_loss_tipo'] = 'porcentaje'
        self.estrategia.config['stop_loss_valor'] = 1.0
        self.estrategia.config['stop_loss_habilitado'] = True
        
        # Abrir operación
        resultado = self.gestor.abrir_operacion(senal_prueba)
        
        if resultado and self.gestor.operaciones_activas:
            operacion = self.gestor.operaciones_activas[0]
            
            # COLOCAR ÓRDENES DE STOP LOSS Y TAKE PROFIT EN BINANCE
            print("\n🎯 Colocando órdenes de Stop Loss y Take Profit...")
            
            # Orden de Take Profit
            tp_orden = self.api.create_order(
                symbol=self.config['activo'],
                side='SELL',
                quantity=operacion['cantidad'],
                order_type='TAKE_PROFIT_MARKET',
                stop_price=operacion['take_profit'],
                reduce_only=True
            )
            
            if tp_orden:
                print(f"✅ Orden Take Profit colocada a {operacion['take_profit']}")
            else:
                print("❌ Error colocando orden Take Profit")
            
            # Orden de Stop Loss
            sl_orden = self.api.create_order(
                symbol=self.config['activo'],
                side='SELL',
                quantity=operacion['cantidad'],
                order_type='STOP_MARKET',
                stop_price=operacion['stop_loss'],
                reduce_only=True
            )
            
            if sl_orden:
                print(f"✅ Orden Stop Loss colocada a {operacion['stop_loss']}")
            else:
                print("❌ Error colocando orden Stop Loss")
            
            return True
        else:
            print("❌ Error ejecutando operación de prueba")
            return False
    
    def obtener_precio_actual(self):
        """Obtener el precio actual del símbolo"""
        try:
            ticker = self.api.client.futures_symbol_ticker(symbol=self.config['activo'])
            return float(ticker['price'])
        except Exception as e:
            print(f"Error obteniendo precio: {e}")
            return None
    
    def verificar_ordenes_activas(self):
        """Verificar órdenes activas en Binance"""
        try:
            ordenes_abiertas = self.api.client.futures_get_open_orders(symbol=self.config['activo'])
            if ordenes_abiertas:
                print("\n📋 Órdenes activas en Binance:")
                for orden in ordenes_abiertas:
                    print(f"   {orden['type']} - Precio: {orden.get('stopPrice', 'N/A')}, Estado: {orden['status']}")
            else:
                print("\n📭 No hay órdenes activas en Binance")
        except Exception as e:
            print(f"Error verificando órdenes: {e}")

async def main():
    bot = TestBot()
    
    # Ejecutar prueba
    exito = await bot.ejecutar_prueba()
    
    if exito:
        # Verificar órdenes activas
        print("\nEsperando 3 segundos para verificar órdenes...")
        await asyncio.sleep(3)
        bot.verificar_ordenes_activas()
        
        # Verificar la operación local
        if bot.gestor.operaciones_activas:
            operacion = bot.gestor.operaciones_activas[0]
            print(f"\n✅ Operación activa:")
            print(f"   ID: {operacion['id']}")
            print(f"   Precio entrada: {operacion['precio_entrada']}")
            print(f"   Stop Loss: {operacion['stop_loss']}")
            print(f"   Take Profit: {operacion['take_profit']}")
            print(f"   Cantidad: {operacion['cantidad']} BTC")
    else:
        print("❌ La prueba falló")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nPrueba interrumpida por el usuario")
    except Exception as e:
        print(f"Error durante la prueba: {e}")