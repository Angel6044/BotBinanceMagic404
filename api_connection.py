import websockets
import json
import asyncio
import hmac
import hashlib
import time
from typing import Dict, Any, Callable
from binance.client import Client
from binance.exceptions import BinanceAPIException
from config import API_KEY, API_SECRET, TESTNET

class APIConnection:
    def __init__(self):
        self.base_url = 'https://testnet.binancefuture.com' if TESTNET else 'https://fapi.binance.com'
        self.ws_url = 'wss://stream.binancefuture.com/ws' if TESTNET else 'wss://fstream.binance.com/ws'
        self.client = Client(API_KEY, API_SECRET, testnet=TESTNET)
        self.ws_connection = None
        self.callbacks = {}
        
    async def connect_websocket(self, streams: list):
        """Conectar a WebSocket con los streams especificados"""
        stream_str = '/'.join(streams)
        url = f"{self.ws_url}/{stream_str}"
        
        try:
            self.ws_connection = await websockets.connect(url)
            print(f"Conectado a WebSocket: {url}")
            
            # Mantener la conexión activa
            while True:
                try:
                    message = await self.ws_connection.recv()
                    data = json.loads(message)
                    
                    # Ejecutar callback correspondiente
                    if 'stream' in data:
                        stream_name = data['stream']
                        if stream_name in self.callbacks:
                            self.callbacks[stream_name](data['data'])
                    else:
                        # Mensaje individual (no multiplexado)
                        if 'e' in data and data['e'] in self.callbacks:
                            self.callbacks[data['e']](data)
                            
                except websockets.exceptions.ConnectionClosed:
                    print("Conexión WebSocket cerrada")
                    break
                except Exception as e:
                    print(f"Error en WebSocket: {e}")
                    break
                    
        except Exception as e:
            print(f"Error conectando a WebSocket: {e}")
    
    def register_callback(self, stream_name: str, callback: Callable):
        """Registrar un callback para un stream específico"""
        self.callbacks[stream_name] = callback
    
    def get_account_info(self):
        """Obtener información de la cuenta"""
        try:
            return self.client.futures_account()
        except BinanceAPIException as e:
            print(f"Error obteniendo información de cuenta: {e}")
            return None
    
    def get_symbol_info(self, symbol: str):
        """Obtener información de un símbolo"""
        try:
            return self.client.futures_exchange_info()
        except BinanceAPIException as e:
            print(f"Error obteniendo información del símbolo: {e}")
            return None
    
    def set_leverage(self, symbol: str, leverage: int):
        """Establecer apalancamiento"""
        try:
            return self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
        except BinanceAPIException as e:
            print(f"Error estableciendo apalancamiento: {e}")
            return None
    
    def set_margin_type(self, symbol: str, margin_type: str):
        """Establecer tipo de margen"""
        try:
            return self.client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
        except BinanceAPIException as e:
            # Ignorar error si ya está configurado al tipo correcto
            if "No need to change margin type" not in str(e):
                print(f"Error estableciendo tipo de margen: {e}")
            return None
    
    def create_order(self, symbol: str, side: str, quantity: float, 
                    order_type: str = 'MARKET', price: float = None, 
                    stop_price: float = None, reduce_only: bool = False):
        """Crear una orden"""
        try:
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type,
                'quantity': quantity,
            }
            
            if price:
                params['price'] = price
            if stop_price:
                params['stopPrice'] = stop_price
            if reduce_only:
                params['reduceOnly'] = True
                
            return self.client.futures_create_order(**params)
        except BinanceAPIException as e:
            print(f"Error creando orden: {e}")
            # Mostrar más detalles del error
            print(f"Parámetros usados: symbol={symbol}, side={side}, quantity={quantity}, type={order_type}")
            if stop_price:
                print(f"stopPrice={stop_price}")
            return None
        except Exception as e:
            print(f"Error inesperado creando orden: {e}")
            return None
    
    def close_position(self, symbol: str, side: str, quantity: float):
        """Cerrar una posición"""
        try:
            # Para cerrar, hacemos la operación contraria
            close_side = 'SELL' if side == 'BUY' else 'BUY'
            return self.create_order(symbol, close_side, quantity, reduce_only=True)
        except BinanceAPIException as e:
            print(f"Error cerrando posición: {e}")
            return None