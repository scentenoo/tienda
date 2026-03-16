from config.database import get_connection


class CashRegister:

    @staticmethod
    def get_movements_by_date(date_str):
        """
        Retorna todos los movimientos de efectivo de un día.
        date_str: 'YYYY-MM-DD'
        Cada movimiento: {tipo, descripcion, monto, hora}
        """
        conn = get_connection()
        cursor = conn.cursor()
        movements = []

        try:
            # 1. Ventas al contado
            cursor.execute("""
                SELECT s.id, s.total, s.created_at
                FROM sales s
                WHERE DATE(s.created_at) = ?
                  AND s.payment_method = 'cash'
                  AND s.status = 'paid'
                ORDER BY s.created_at ASC
            """, (date_str,))

            for row in cursor.fetchall():
                movements.append({
                    'tipo': 'Venta contado',
                    'descripcion': f'Venta #{row["id"]}',
                    'monto': row['total'],
                    'hora': row['created_at'],
                })

            # 2. Abonos de clientes fiados (credit con amount negativo → ABS)
            cursor.execute("""
                SELECT ct.id, ct.amount, ct.description, ct.created_at,
                       c.name as client_name
                FROM client_transactions ct
                LEFT JOIN clients c ON ct.client_id = c.id
                WHERE DATE(ct.created_at) = ?
                  AND ct.transaction_type = 'credit'
                ORDER BY ct.created_at ASC
            """, (date_str,))

            for row in cursor.fetchall():
                monto = abs(row['amount'])
                movements.append({
                    'tipo': 'Abono cliente',
                    'descripcion': f"{row['client_name']} — {row['description']}",
                    'monto': monto,
                    'hora': row['created_at'],
                })

            # Ordenar por hora
            movements.sort(key=lambda x: x['hora'])
            return movements

        except Exception as e:
            print(f"Error en CashRegister.get_movements_by_date: {e}")
            return []
        finally:
            conn.close()

    @staticmethod
    def get_daily_total(date_str):
        """Retorna el total en efectivo de un día."""
        movements = CashRegister.get_movements_by_date(date_str)
        return sum(m['monto'] for m in movements)

    @staticmethod
    def get_daily_summary(date_str):
        """Retorna resumen del día: total_contado, total_abonos, total_general."""
        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT COALESCE(SUM(total), 0)
                FROM sales
                WHERE DATE(created_at) = ?
                  AND payment_method = 'cash'
                  AND status = 'paid'
            """, (date_str,))
            total_contado = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(ABS(amount)), 0)
                FROM client_transactions
                WHERE DATE(created_at) = ?
                  AND transaction_type = 'credit'
            """, (date_str,))
            total_abonos = cursor.fetchone()[0]

            return {
                'fecha': date_str,
                'total_contado': total_contado,
                'total_abonos': total_abonos,
                'total_general': total_contado + total_abonos,
            }

        except Exception as e:
            print(f"Error en CashRegister.get_daily_summary: {e}")
            return {
                'fecha': date_str,
                'total_contado': 0.0,
                'total_abonos': 0.0,
                'total_general': 0.0,
            }
        finally:
            conn.close()

    @staticmethod
    def get_history(days=30):
        """
        Retorna resumen de los últimos N días que tuvieron movimientos.
        Cada entrada: {fecha, total_contado, total_abonos, total_general}
        """
        conn = get_connection()
        cursor = conn.cursor()

        try:
            # Fechas con ventas al contado
            cursor.execute("""
                SELECT DATE(created_at) as fecha,
                       COALESCE(SUM(total), 0) as total_contado
                FROM sales
                WHERE payment_method = 'cash'
                  AND status = 'paid'
                  AND DATE(created_at) >= DATE('now', ?)
                GROUP BY DATE(created_at)
            """, (f'-{days} days',))
            contado_by_date = {row['fecha']: row['total_contado'] for row in cursor.fetchall()}

            # Fechas con abonos
            cursor.execute("""
                SELECT DATE(created_at) as fecha,
                       COALESCE(SUM(ABS(amount)), 0) as total_abonos
                FROM client_transactions
                WHERE transaction_type = 'credit'
                  AND DATE(created_at) >= DATE('now', ?)
                GROUP BY DATE(created_at)
            """, (f'-{days} days',))
            abonos_by_date = {row['fecha']: row['total_abonos'] for row in cursor.fetchall()}

            # Unir todas las fechas
            all_dates = sorted(
                set(contado_by_date.keys()) | set(abonos_by_date.keys()),
                reverse=True
            )

            history = []
            for fecha in all_dates:
                tc = contado_by_date.get(fecha, 0.0)
                ta = abonos_by_date.get(fecha, 0.0)
                history.append({
                    'fecha': fecha,
                    'total_contado': tc,
                    'total_abonos': ta,
                    'total_general': tc + ta,
                })

            return history

        except Exception as e:
            print(f"Error en CashRegister.get_history: {e}")
            return []
        finally:
            conn.close()