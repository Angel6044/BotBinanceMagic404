import pandas as pd
import numpy as np
import talib
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from config import CONFIG_TRADING

@dataclass
class Signal:
    tipo: str #'long' o 'short'
    precio: float
    timestamp: int
    atr: float = 0.0

class EstrategiaMACD:
    def __init__(self):
        self.config = CONFIG_TRADING
        self.datos_1m = pd.DataFrame()
        self.datos_macd = pd.DataFrame()
        self.macd_aligned = pd.DataFrame()
        
    def agregar_dato_ohlcv(self, timestamp: int, open: float, high: float, low: float, close: float, volume: float, timeframe: str):
        """Agregar datos OHLCV a los DataFrames correspondientes"""
        nuevo_dato = pd.DataFrame({
            'timestamp': [timestamp],
            'open': [open],
            'high': [high],
            'low': [low],
            'close': [close],
            'volume': [volume]
        })
        nuevo_dato.set_index('timestamp', inplace=True)
        
        if timeframe == self.config['temporalidad_operaciones']:
            self.datos_1m = pd.concat([self.datos_1m, nuevo_dato])
            # Limpiar datos antiguos para optimizar memoria
            if len(self.datos_1m) > 1000:
                self.datos_1m = self.datos_1m.iloc[-500:]
                
        elif timeframe == self.config['temporalidad_macd']:
            self.datos_macd = pd.concat([self.datos_macd, nuevo_dato])
            # Calcular MACD cuando tengamos suficientes datos
            if len(self.datos_macd) > self.config['macd_slow'] + 10:
                self.calcular_macd()
                # Alinear MACD con datos de 1m
                if not self.datos_1m.empty:
                    self.alinear_macd()
    
    def calcular_macd(self):
        """Calcular indicadores MACD"""
        if len(self.datos_macd) < self.config['macd_slow'] + 10:
            return
            
        close_prices = self.datos_macd['close'].ffill()
        
        # Calcular MACD
        macd, signal, hist = talib.MACD(
            close_prices,
            fastperiod=self.config['macd_fast'],
            slowperiod=self.config['macd_slow'],
            signalperiod=self.config['macd_signal']
        )
        
        self.datos_macd['macd'] = macd
        self.datos_macd['signal'] = signal
        self.datos_macd['histogram'] = hist
        
        # Calcular ATR
        self.datos_macd['atr'] = talib.ATR(
            self.datos_macd['high'].ffill(),
            self.datos_macd['low'].ffill(),
            self.datos_macd['close'].ffill(),
            timeperiod=self.config['atr_periodo']
        )
        
        # Rellenar valores NaN
        self.datos_macd = self.datos_macd.ffill()
    
    def alinear_macd(self):
        """Alinear datos MACD con el timeframe de operaciones"""
        if self.datos_macd.empty or self.datos_1m.empty:
            return
            
        # Reindexar datos MACD al índice de 1m usando forward fill
        self.macd_aligned = self.datos_macd.reindex(self.datos_1m.index, method='ffill')
    
    def generar_senal(self) -> Optional[Signal]:
        # SEÑAL DE PRUEBA - descomenta la siguiente línea para testing
        #return Signal(tipo='long', precio=50000, timestamp=int(time.time()*1000), atr=200)

        
        # Generar señal de trading basada en MACD
        
        if self.macd_aligned.empty or len(self.macd_aligned) < 2:
            return None
            
        # Obtener los últimos dos valores alineados
        current = self.macd_aligned.iloc[-1]
        previous = self.macd_aligned.iloc[-2]
        
        # Verificar que tenemos todos los datos necesarios
        if any(pd.isna([current['macd'], current['signal'], previous['macd'], previous['signal']])):
            return None
        
        # Precio actual
        current_price = self.datos_1m.iloc[-1]['close']
        current_atr = current['atr'] if not pd.isna(current['atr']) else 0
        
        # Señal LONG: MACD cruza por encima de la señal
        if current['macd'] > current['signal'] and previous['macd'] <= previous['signal']:
            return Signal(tipo='long', precio=current_price, timestamp=self.datos_1m.index[-1], atr=current_atr)
        
        # Señal SHORT: MACD cruza por debajo de la señal
        elif current['macd'] < current['signal'] and previous['macd'] >= previous['signal']:
            return Signal(tipo='short', precio=current_price, timestamp=self.datos_1m.index[-1], atr=current_atr)
        
        return None
        
    
    def calcular_stop_loss_take_profit(self, entry_price: float, atr: float, direction: str) -> Tuple[float, float]:
        #Calcular stop loss y take profit según configuración
        # Take Profit
        if self.config['take_profit_tipo'] == 'atr':
            if direction == 'long':
                take_profit = entry_price + (atr * self.config['take_profit_valor'])
            else:
                take_profit = entry_price - (atr * self.config['take_profit_valor'])
        else:  # porcentaje
            tp_percentage = self.config['take_profit_valor'] / 100
            if direction == 'long':
                take_profit = entry_price * (1 + tp_percentage)
            else:
                take_profit = entry_price * (1 - tp_percentage)
        
        # Stop Loss
        if self.config['stop_loss_habilitado']:
            if self.config['stop_loss_tipo'] == 'rr_ratio':
                # Misma distancia que el take profit (1:1 risk-reward)
                if direction == 'long':
                    stop_loss = entry_price - (take_profit - entry_price)
                else:
                    stop_loss = entry_price + (entry_price - take_profit)
            else:  # porcentaje
                sl_percentage = self.config['stop_loss_valor'] / 100
                if direction == 'long':
                    stop_loss = entry_price * (1 - sl_percentage)
                else:
                    stop_loss = entry_price * (1 + sl_percentage)
        else:
            stop_loss = 0.0  # No usar stop loss
        
        return round(stop_loss, 2), round(take_profit, 2)
    
    """
    def calcular_stop_loss_take_profit(self, entry_price: float, atr: float, direction: str) -> Tuple[float, float]:
        # Calcular stop loss y take profit según configuración
        # Si no tenemos estrategia (prueba), usar valores por defecto
        if not hasattr(self, 'estrategia') or self.estrategia is None:
            # Para pruebas: TP y SL al 1%
            if direction == 'long':
                take_profit = entry_price * 1.01
                stop_loss = entry_price * 0.99
            else:
                take_profit = entry_price * 0.99
                stop_loss = entry_price * 1.01
            return round(stop_loss, 2), round(take_profit, 2)
    """