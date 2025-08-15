from tkinter import messagebox

def validate_number(value):
    """Valida que el valor sea un número válido"""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False
    
def parse_currency_to_float(value):
    """
    Convierte un valor monetario formateado a float
    Maneja formatos como: "700,000.00", "$1,234.56", "1.234,56", etc.
    """
    if value is None:
        return 0.0
    
    # Si ya es un número, devolverlo
    if isinstance(value, (int, float)):
        return float(value)
    
    # Convertir a string y limpiar
    value_str = str(value).strip()
    
    # Remover símbolos de moneda y espacios
    value_str = value_str.replace('$', '').replace('€', '').replace('£', '').strip()
    
    # Si está vacío después de limpiar, devolver 0
    if not value_str:
        return 0.0
    
    try:
        # Detectar el formato del número
        # Si tiene coma como último separador (formato español: 1.234,56)
        if ',' in value_str and '.' in value_str:
            # Formato con miles separados por punto y decimales por coma
            if value_str.rindex(',') > value_str.rindex('.'):
                # Formato: 1.234.567,89 (español)
                value_str = value_str.replace('.', '').replace(',', '.')
            else:
                # Formato: 1,234,567.89 (inglés)
                value_str = value_str.replace(',', '')
        elif ',' in value_str:
            # Solo tiene comas
            # Verificar si es separador de miles o decimales
            comma_parts = value_str.split(',')
            if len(comma_parts) == 2 and len(comma_parts[1]) <= 2:
                # Probablemente decimales: 123,45
                value_str = value_str.replace(',', '.')
            else:
                # Probablemente separador de miles: 1,234,567
                value_str = value_str.replace(',', '')
        
        return float(value_str)
    
    except (ValueError, AttributeError) as e:
        print(f"Error al convertir '{value}' a float: {e}")
        return 0.0

def validate_positive(value, field_name):
    """Valida que un valor sea un número positivo"""
    try:
        # Usar la nueva función de conversión
        num_value = safe_float_conversion(value, field_name)
        
        if num_value <= 0:
            from tkinter import messagebox
            messagebox.showerror("Error de Validación", 
                               f"{field_name} debe ser un número positivo mayor que 0")
            return None
        
        return num_value
        
    except ValueError as e:
        from tkinter import messagebox
        messagebox.showerror("Error de Validación", str(e))
        return None
    except Exception as e:
        from tkinter import messagebox
        messagebox.showerror("Error de Validación", 
                           f"Error al validar {field_name}: {str(e)}")
        return None

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

def safe_float_conversion(value, field_name="valor"):
    """
    Conversión segura de string a float con manejo de errores
    """
    try:
        return parse_currency_to_float(value)
    except Exception as e:
        raise ValueError(f"Error en {field_name}: No se pudo convertir '{value}' a número válido")

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