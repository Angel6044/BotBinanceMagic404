import pandas as pd
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from api_connection import APIConnection
from estrategia import EstrategiaMACD, Signal
from config import CONFIG_TRADING, ARCHIVO_OPERACIONES

class GestorOperaciones:
    def __init__(self, api: APIConnection, estrategia: EstrategiaMACD):
        self.api = api
        self.estrategia = estrategia
        self.config = CONFIG_TRADING
        self.operaciones_activas = []
        self.operaciones_cerradas = []
        self.archivo_operaciones = ARCHIVO_OPERACIONES
        self.inicializar_archivo()
        
    def inicializar_archivo(self):
        """Inicializar archivo CSV para operaciones si no existe"""
        try:
            with open(self.archivo_operaciones, 'x') as f:
                f.write("timestamp,operacion,activo,direccion,precio_entrada,cantidad,stop_loss,take_profit,precio_salida,comision,pnl,pnl_percentaje,razon_cierre\n")
        except FileExistsError:
            pass  # El archivo ya existe, no hay problema
    
    def guardar_operacion(self, operacion: Dict):
        """Guardar operación en archivo CSV"""
        try:
            with open(self.archivo_operaciones, 'a') as f:
                f.write(f"{operacion['timestamp']},{operacion['id']},{operacion['activo']},"
                        f"{operacion['direccion']},{operacion['precio_entrada']},{operacion['cantidad']},"
                        f"{operacion.get('stop_loss', '')},{operacion.get('take_profit', '')},"
                        f"{operacion.get('precio_salida', '')},{operacion.get('comision', 0)},"
                        f"{operacion.get('pnl', 0)},{operacion.get('pnl_percentaje', 0)},"
                        f"{operacion.get('razon_cierre', '')}\n")
        except Exception as e:
            print(f"Error guardando operación: {e}")
    
    def configurar_cuenta(self):
        """Configurar cuenta con apalancamiento y tipo de margen"""
        print("Configurando cuenta...")
        
        # Establecer apalancamiento
        resultado = self.api.set_leverage(self.config['activo'], self.config['apalancamiento'])
        if resultado:
            print(f"Apalancamiento establecido a {self.config['apalancamiento']}x")
        
        # Establecer tipo de margen
        resultado = self.api.set_margin_type(self.config['activo'], self.config['tipo_margen'])
        if resultado:
            print(f"Tipo de margen establecido a {self.config['tipo_margen']}")
    
    def calcular_cantidad(self, precio: float) -> float:
        """Calcular cantidad a operar basado en el monto configurado"""
        # Para futuros, la cantidad es en el activo subyacente
        monto = self.config['monto_operacion']
        cantidad_cruda = monto / precio
        
        # Obtener información de precisión del símbolo
        try:
            # Obtener información del exchange
            exchange_info = self.api.client.futures_exchange_info()
            symbol_info = None
            
            for symbol in exchange_info['symbols']:
                if symbol['symbol'] == self.config['activo']:
                    symbol_info = symbol
                    break
            
            if symbol_info:
                # Encontrar el filtro de LOT_SIZE
                lot_size_filter = None
                for filtro in symbol_info['filters']:
                    if filtro['filterType'] == 'LOT_SIZE':
                        lot_size_filter = filtro
                        break
                
                if lot_size_filter:
                    # Obtener step size (precisión permitida)
                    step_size = float(lot_size_filter['stepSize'])
                    # Redondear a la precisión permitida
                    cantidad_ajustada = round(cantidad_cruda / step_size) * step_size
                    print(f"Cantidad cruda: {cantidad_cruda}, Ajustada: {cantidad_ajustada}")
                    return cantidad_ajustada
        
        except Exception as e:
            print(f"Error obteniendo información de precisión: {e}")
        
        # Fallback: redondear a 6 decimales
        return round(cantidad_cruda, 6)
    
    def obtener_precio_entrada_real(self, orden: dict) -> float:
        """Obtener el precio real de entrada de la orden"""
        try:
            # Intentar obtener el precio promedio de la orden
            if 'avgPrice' in orden and orden['avgPrice']:
                return float(orden['avgPrice'])
            
            # Si no está disponible, obtener el precio actual
            ticker = self.api.client.futures_symbol_ticker(symbol=self.config['activo'])
            return float(ticker['price'])
            
        except Exception as e:
            print(f"Error obteniendo precio de entrada real: {e}")
            return 0

    def abrir_operacion(self, senal: Signal) -> bool:
        """Abrir una nueva operación basada en una señal"""
        if len(self.operaciones_activas) >= self.config['max_operaciones_simultaneas']:
            print("Máximo de operaciones simultáneas alcanzado")
            return False
        
        print(f"Procesando señal: {senal.tipo} a precio {senal.precio}")
        
        # Calcular cantidad
        cantidad = self.calcular_cantidad(senal.precio)
        print(f"Cantidad calculada: {cantidad} {self.config['activo'].replace('USDT', '')}")
        
        if cantidad <= 0:
            print("Cantidad inválida para operar")
            return False
        
        # Determinar lado de la operación
        lado = 'BUY' if senal.tipo == 'long' else 'SELL'
        
        # Calcular stop loss y take profit BASADO EN EL PRECIO DE SEÑAL (temporal)
        if hasattr(self, 'estrategia') and self.estrategia is not None:
            stop_loss, take_profit = self.estrategia.calcular_stop_loss_take_profit(
                senal.precio, senal.atr, senal.tipo
            )
        else:
            # Fallback para pruebas
            if senal.tipo == 'long':
                take_profit = senal.precio * 1.01
                stop_loss = senal.precio * 0.99
            else:
                take_profit = senal.precio * 0.99
                stop_loss = senal.precio * 1.01
        
        print(f"Stop Loss calculado: {stop_loss}, Take Profit calculado: {take_profit}")
        
        # Crear orden
        orden = self.api.create_order(
            symbol=self.config['activo'],
            side=lado,
            quantity=cantidad,
            order_type='MARKET'
        )
        
        if not orden:
            print("Error creando orden")
            return False
        
        # Obtener el precio real de ejecución
        precio_entrada_real = self.obtener_precio_entrada_real(orden)
        if precio_entrada_real == 0:
            print("⚠️  Advertencia: No se pudo obtener el precio de entrada real, usando precio de señal")
            precio_entrada_real = senal.precio
        
        # RECALCULAR STOP LOSS Y TAKE PROFIT CON EL PRECIO REAL
        if hasattr(self, 'estrategia') and self.estrategia is not None:
            stop_loss, take_profit = self.estrategia.calcular_stop_loss_take_profit(
                precio_entrada_real, senal.atr, senal.tipo
            )
        else:
            if senal.tipo == 'long':
                take_profit = precio_entrada_real * 1.01
                stop_loss = precio_entrada_real * 0.99
            else:
                take_profit = precio_entrada_real * 0.99
                stop_loss = precio_entrada_real * 1.01
        
        # Registrar operación
        operacion = {
            'id': orden['orderId'],
            'timestamp': int(time.time() * 1000),
            'activo': self.config['activo'],
            'direccion': senal.tipo,
            'precio_entrada': precio_entrada_real,
            'cantidad': cantidad,
            'stop_loss': stop_loss,
            'take_profit': take_profit,
            'comision': float(orden.get('commission', 0)),
            'estado': 'abierta'
        }
        
        self.operaciones_activas.append(operacion)
        self.guardar_operacion(operacion)
        print(f"✅ Operación {senal.tipo} abierta a {precio_entrada_real}")
        print(f"   Stop Loss: {stop_loss}")
        print(f"   Take Profit: {take_profit}")
        print(f"   Cantidad: {cantidad} {self.config['activo'].replace('USDT', '')}")
        
        # COLOCAR ÓRDENES DE STOP LOSS Y TAKE PROFIT EN BINANCE
        print("\n🎯 Colocando órdenes de Stop Loss y Take Profit...")
        
        # Orden de Take Profit
        tp_orden = self.api.create_order(
            symbol=self.config['activo'],
            side='SELL' if senal.tipo == 'long' else 'BUY',
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
            side='SELL' if senal.tipo == 'long' else 'BUY',
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
    
    def colocar_ordenes_stop(self, operacion: Dict):
        """Colocar órdenes de stop loss y take profit en Binance"""
        try:
            # Orden de Take Profit
            tp_orden = self.api.create_order(
                symbol=operacion['activo'],
                side='SELL' if operacion['direccion'] == 'long' else 'BUY',
                quantity=operacion['cantidad'],
                order_type='TAKE_PROFIT_MARKET',
                stop_price=operacion['take_profit'],
                reduce_only=True
            )
            
            if tp_orden:
                print(f"✅ Orden Take Profit colocada a {operacion['take_profit']}")
            
            # Orden de Stop Loss
            sl_orden = self.api.create_order(
                symbol=operacion['activo'],
                side='SELL' if operacion['direccion'] == 'long' else 'BUY',
                quantity=operacion['cantidad'],
                order_type='STOP_MARKET',
                stop_price=operacion['stop_loss'],
                reduce_only=True
            )
            
            if sl_orden:
                print(f"✅ Orden Stop Loss colocada a {operacion['stop_loss']}")
                
        except Exception as e:
            print(f"Error colocando órdenes de stop: {e}")
    
    def verificar_cierre_operaciones(self, precio_actual: float):
        """Verificar si alguna operación activa debe cerrarse"""
        for operacion in self.operaciones_activas[:]:
            if operacion['estado'] == 'open':
                debe_cerrar = False
                razon = ""
                
                if operacion['direccion'] == 'long':
                    # Verificar take profit
                    if precio_actual >= operacion['take_profit']:
                        debe_cerrar = True
                        razon = "take_profit"
                    # Verificar stop loss
                    elif operacion['stop_loss'] > 0 and precio_actual <= operacion['stop_loss']:
                        debe_cerrar = True
                        razon = "stop_loss"
                        
                else:  # short
                    # Verificar take profit
                    if precio_actual <= operacion['take_profit']:
                        debe_cerrar = True
                        razon = "take_profit"
                    # Verificar stop loss
                    elif operacion['stop_loss'] > 0 and precio_actual >= operacion['stop_loss']:
                        debe_cerrar = True
                        razon = "stop_loss"
                
                if debe_cerrar:
                    self.cerrar_operacion(operacion, precio_actual, razon)
    
    def cerrar_operacion(self, operacion: Dict, exit_price: float, reason: str):
        """Cerrar una operación"""
        # Determinar lado para cerrar (opuesto al de entrada)
        lado_cierre = 'SELL' if operacion['direccion'] == 'long' else 'BUY'
        
        # Crear orden de cierre
        orden = self.api.create_order(
            symbol=operacion['activo'],
            side=lado_cierre,
            quantity=operacion['cantidad'],
            order_type='MARKET',
            reduce_only=True  # Solo reducir posición, no abrir contraria
        )
        
        if not orden:
            print("Error cerrando operación")
            return
        
        # Calcular PNL
        precio_cierre = self.obtener_precio_entrada_real(orden)
        if precio_cierre == 0:
            precio_cierre = exit_price
            
        if operacion['direccion'] == 'long':
            pnl = (precio_cierre - operacion['precio_entrada']) * operacion['cantidad']
        else:
            pnl = (operacion['precio_entrada'] - precio_cierre) * operacion['cantidad']
        
        pnl_percentaje = (pnl / (operacion['precio_entrada'] * operacion['cantidad'])) * 100
        
        # Actualizar operación
        operacion['precio_salida'] = precio_cierre
        operacion['comision'] += float(orden.get('commission', 0))
        operacion['pnl'] = pnl
        operacion['pnl_percentaje'] = pnl_percentaje
        operacion['razon_cierre'] = reason
        operacion['estado'] = 'cerrada'
        operacion['timestamp_cierre'] = int(time.time() * 1000)
        
        # Mover a operaciones cerradas
        self.operaciones_activas.remove(operacion)
        self.operaciones_cerradas.append(operacion)
        
        # Actualizar archivo
        self.guardar_operacion(operacion)
        
        print(f"Operación {operacion['direccion']} cerrada: {reason}, PNL: {pnl:.2f} USDT ({pnl_percentaje:.2f}%)")