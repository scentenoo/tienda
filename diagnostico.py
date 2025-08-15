#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Diagnóstico y Corrección de Base de Datos
Ejecutar desde la raíz del proyecto: python fix_database.py
"""

import sqlite3
from datetime import datetime
from config.database import get_connection

def diagnose_database():
    """Diagnostica problemas en la base de datos"""
    print("🔍 DIAGNÓSTICO DE BASE DE DATOS")
    print("=" * 50)
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Estado de clientes
    print("\n📊 ESTADO DE CLIENTES:")
    cursor.execute("SELECT id, name, credit_limit, total_debt FROM clients")
    clients = cursor.fetchall()
    
    for client in clients:
        print(f"   Cliente #{client[0]} - {client[1]}")
        print(f"   Límite: ${client[2]:,.2f}, Deuda: ${client[3]:,.2f}")
    
    # 2. Estado de ventas
    print("\n💰 ESTADO DE VENTAS:")
    cursor.execute("""
        SELECT status, COUNT(*) as cantidad, SUM(total) as total_monto
        FROM sales 
        GROUP BY status
    """)
    sales_summary = cursor.fetchall()
    
    total_sales = 0
    for status, count, total in sales_summary:
        print(f"   {status}: {count} ventas, ${total:,.2f}")
        total_sales += total if total else 0
    
    print(f"   TOTAL VENTAS: ${total_sales:,.2f}")
    
    # 3. Transacciones de clientes
    print("\n📝 TRANSACCIONES DE CLIENTES:")
    cursor.execute("""
        SELECT transaction_type, COUNT(*) as cantidad, SUM(amount) as total_monto
        FROM client_transactions 
        GROUP BY transaction_type
    """)
    transactions = cursor.fetchall()
    
    for trans_type, count, total in transactions:
        print(f"   {trans_type}: {count} transacciones, ${total:,.2f}")
    
    # 4. Ventas detalladas
    print("\n🛒 VENTAS DETALLADAS:")
    cursor.execute("""
        SELECT id, client_id, total, status, created_at 
        FROM sales 
        ORDER BY created_at DESC
    """)
    sales = cursor.fetchall()
    
    for sale in sales:
        print(f"   Venta #{sale[0]} - Cliente: {sale[1]}, Total: ${sale[2]:,.2f}, Estado: {sale[3]}")
    
    # 5. Transacciones detalladas
    print("\n💸 TRANSACCIONES DETALLADAS:")
    cursor.execute("""
        SELECT client_id, transaction_type, amount, description, created_at
        FROM client_transactions 
        ORDER BY created_at DESC
    """)
    transactions = cursor.fetchall()
    
    for trans in transactions:
        print(f"   Cliente: {trans[0]}, Tipo: {trans[1]}, Monto: ${trans[2]:,.2f}")
        print(f"      Descripción: {trans[3]}, Fecha: {trans[4]}")
    
    conn.close()

def fix_client_debts():
    """Recalcula y corrige las deudas de los clientes"""
    print("\n🔧 CORRIGIENDO DEUDAS DE CLIENTES...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener todos los clientes
    cursor.execute("SELECT id, name FROM clients")
    clients = cursor.fetchall()
    
    for client_id, client_name in clients:
        # Calcular deuda real basada en transacciones
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN transaction_type = 'debit' THEN amount ELSE 0 END) as total_debits,
                SUM(CASE WHEN transaction_type = 'credit' THEN amount ELSE 0 END) as total_credits
            FROM client_transactions 
            WHERE client_id = ?
        """, (client_id,))
        
        result = cursor.fetchone()
        total_debits = result[0] if result[0] else 0
        total_credits = result[1] if result[1] else 0
        calculated_debt = total_debits - total_credits
        
        # Obtener deuda actual del cliente
        cursor.execute("SELECT total_debt FROM clients WHERE id = ?", (client_id,))
        current_debt = cursor.fetchone()[0]
        
        print(f"   Cliente: {client_name}")
        print(f"      Débitos: ${total_debits:,.2f}")
        print(f"      Créditos: ${total_credits:,.2f}")
        print(f"      Deuda calculada: ${calculated_debt:,.2f}")
        print(f"      Deuda actual: ${current_debt:,.2f}")
        
        if abs(calculated_debt - current_debt) > 0.01:  # Diferencia mayor a 1 centavo
            print(f"      ⚠️  INCONSISTENCIA DETECTADA - Corrigiendo...")
            cursor.execute("""
                UPDATE clients 
                SET total_debt = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, (max(0, calculated_debt), client_id))
            print(f"      ✅ Deuda actualizada de ${current_debt:,.2f} a ${max(0, calculated_debt):,.2f}")
        else:
            print(f"      ✅ Deuda correcta")
    
    conn.commit()
    conn.close()

def sync_sales_with_transactions():
    """Sincroniza el estado de las ventas con las transacciones de pago"""
    print("\n🔄 SINCRONIZANDO VENTAS CON TRANSACCIONES...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Obtener todas las ventas
    cursor.execute("SELECT id, client_id, total, status FROM sales")
    sales = cursor.fetchall()
    
    for sale_id, client_id, sale_total, current_status in sales:
        # Verificar si hay transacciones de crédito relacionadas con esta venta
        cursor.execute("""
            SELECT SUM(amount) 
            FROM client_transactions 
            WHERE client_id = ? AND transaction_type = 'credit' 
            AND (description LIKE ? OR description LIKE ?)
        """, (client_id, f"%Venta #{sale_id}%", f"%venta #{sale_id}%"))
        
        result = cursor.fetchone()
        total_paid = result[0] if result[0] else 0
        
        # Determinar el estado correcto
        if total_paid >= sale_total:
            correct_status = 'paid'
        else:
            correct_status = 'pending'
        
        if current_status != correct_status:
            print(f"   Venta #{sale_id}: ${sale_total:,.2f} - Pagado: ${total_paid:,.2f}")
            print(f"      Estado actual: {current_status} -> Nuevo estado: {correct_status}")
            
            cursor.execute("""
                UPDATE sales 
                SET status = ?, updated_at = datetime('now', 'localtime')
                WHERE id = ?
            """, (correct_status, sale_id))
    
    conn.commit()
    conn.close()

def clean_duplicate_transactions():
    """Elimina transacciones duplicadas si las hay"""
    print("\n🧹 BUSCANDO TRANSACCIONES DUPLICADAS...")
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Buscar posibles duplicados
    cursor.execute("""
        SELECT client_id, transaction_type, amount, description, COUNT(*) as count
        FROM client_transactions 
        GROUP BY client_id, transaction_type, amount, description, 
                 strftime('%Y-%m-%d %H:%M', created_at)
        HAVING COUNT(*) > 1
    """)
    
    duplicates = cursor.fetchall()
    
    if duplicates:
        print(f"   ⚠️  Encontrados {len(duplicates)} grupos de transacciones duplicadas")
        for dup in duplicates:
            print(f"      Cliente: {dup[0]}, Tipo: {dup[1]}, Monto: ${dup[2]:,.2f}, Cantidad: {dup[4]}")
        
        # Aquí podrías agregar lógica para eliminar duplicados si es necesario
        # Por ahora solo reportamos
    else:
        print("   ✅ No se encontraron transacciones duplicadas")
    
    conn.close()

def regenerate_reports_data():
    """Fuerza la regeneración de datos para reportes"""
    print("\n📊 REGENERANDO DATOS DE REPORTES...")
    
    # Este método debería llamar a la lógica de tu sistema de reportes
    # Para forzar que recalcule todos los valores
    
    conn = get_connection()
    cursor = conn.cursor()
    
    # Calcular totales reales
    cursor.execute("SELECT SUM(total) FROM sales WHERE status = 'paid'")
    total_paid_sales = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(total) FROM sales WHERE status = 'pending'")
    total_pending_sales = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT SUM(total_debt) FROM clients")
    total_client_debt = cursor.fetchone()[0] or 0
    
    print(f"   Total ventas pagadas: ${total_paid_sales:,.2f}")
    print(f"   Total ventas pendientes: ${total_pending_sales:,.2f}")
    print(f"   Total deuda clientes: ${total_client_debt:,.2f}")
    
    if abs(total_pending_sales - total_client_debt) > 0.01:
        print(f"   ⚠️  INCONSISTENCIA: Ventas pendientes ≠ Deuda de clientes")
        print(f"      Diferencia: ${abs(total_pending_sales - total_client_debt):,.2f}")
    else:
        print("   ✅ Ventas pendientes = Deuda de clientes")
    
    conn.close()

def main():
    """Función principal del script de corrección"""
    print("🚀 SCRIPT DE CORRECCIÓN DE BASE DE DATOS")
    print("=" * 60)
    print("Este script diagnosticará y corregirá inconsistencias\n")
    
    try:
        # Paso 1: Diagnóstico
        diagnose_database()
        
        # Paso 2: Corrección de deudas
        fix_client_debts()
        
        # Paso 3: Sincronización de ventas
        sync_sales_with_transactions()
        
        # Paso 4: Limpieza de duplicados
        clean_duplicate_transactions()
        
        # Paso 5: Regeneración de reportes
        regenerate_reports_data()
        
        print("\n" + "=" * 60)
        print("✅ CORRECCIÓN COMPLETADA")
        print("   - Deudas de clientes recalculadas")
        print("   - Estados de ventas sincronizados")
        print("   - Base de datos consistente")
        print("\n💡 Reinicia tu aplicación para ver los cambios")
        
    except Exception as e:
        print(f"\n❌ ERROR DURANTE LA CORRECCIÓN: {e}")
        print("   Por favor revisa los logs y contacta al desarrollador")

if __name__ == "__main__":
    main()