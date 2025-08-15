def format_currency(amount):
    """Formatea un número como moneda"""
    try:
        # Asegurar que sea float
        if isinstance(amount, str):
            # Si viene como string, usar la función de conversión
            from utils.validators import parse_currency_to_float
            amount = parse_currency_to_float(amount)
        
        amount = float(amount) if amount is not None else 0.0
        
        # Formatear como moneda sin comas (para evitar confusión)
        return f"${amount:,.2f}"
        
    except (ValueError, TypeError):
        return "$0.00"

def format_number(number):
    """Formatea un número con separadores de miles"""
    try:
        # Asegurar que sea numérico
        if isinstance(number, str):
            from utils.validators import parse_currency_to_float
            number = parse_currency_to_float(number)
            
        number = float(number) if number is not None else 0.0
        
        # Para enteros, no mostrar decimales
        if number == int(number):
            return f"{int(number):,}"
        else:
            return f"{number:,.2f}"
            
    except (ValueError, TypeError):
        return "0"

def unformat_currency(formatted_value):
    """Convierte un valor formateado de vuelta a float"""
    try:
        from utils.validators import parse_currency_to_float
        return parse_currency_to_float(formatted_value)
    except:
        return 0.0