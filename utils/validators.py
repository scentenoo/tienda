def validate_number(value):
    """Valida que el valor sea un número válido"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False

def validate_positive(value):
    """Valida que el valor sea un número positivo"""
    try:
        num = float(value)
        return num > 0
    except (ValueError, TypeError):
        return False

def validate_email(email):
    """Valida formato básico de email"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_phone(phone):
    """Valida formato básico de teléfono"""
    import re
    # Acepta formatos como: 123-456-7890, (123) 456-7890, 123.456.7890, 1234567890
    pattern = r'^[\+]?[1-9]?[\d\s\-\(\)\.]{7,15}$'
    return re.match(pattern, phone.strip()) is not None

def validate_required(value):
    """Valida que el campo no esté vacío"""
    return value is not None and str(value).strip() != ""

def validate_length(value, min_length=0, max_length=None):
    """Valida la longitud de una cadena"""
    if not validate_required(value):
        return min_length == 0
    
    length = len(str(value).strip())
    if length < min_length:
        return False
    if max_length is not None and length > max_length:
        return False
    return True