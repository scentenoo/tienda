# Agregar al inicio de tu aplicación o en un archivo de configuración

import locale
import os

def setup_regional_format():
    """Configura el formato regional para números"""
    try:
        # Intentar configurar locale español para Colombia
        locale.setlocale(locale.LC_ALL, 'es_CO.UTF-8')
    except locale.Error:
        try:
            # Fallback a español genérico
            locale.setlocale(locale.LC_ALL, 'Spanish_Colombia.1252')
        except locale.Error:
            try:
                # Otro fallback
                locale.setlocale(locale.LC_ALL, 'es_ES.UTF-8')
            except locale.Error:
                # Usar el locale por defecto del sistema
                locale.setlocale(locale.LC_ALL, '')
                
def format_currency_locale(amount):
    """Formatea moneda usando la configuración regional"""
    try:
        amount = float(amount) if amount is not None else 0.0
        return locale.currency(amount, grouping=True)
    except:
        return f"${amount:,.2f}"