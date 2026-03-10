# 🛒 Sistema de Gestión Comercial

Sistema de escritorio para la gestión integral de un negocio comercial, desarrollado en Python con base de datos SQLite. Actualmente en uso activo en producción.

---

## 📌 Descripción

Aplicación de escritorio con interfaz gráfica que centraliza las operaciones de un negocio: ventas, compras, inventario, clientes y control de pérdidas. Implementa un sistema de autenticación con roles diferenciados para administrador y empleado.

---

## ⚙️ Funcionalidades

**Ventas**
- Registro detallado de ventas con fecha, hora y productos vendidos
- Asociación de ventas a clientes registrados o venta al contado
- Historial completo de transacciones

**Compras**
- Registro de compras con soporte para flete e IVA
- Control de proveedores y costos de adquisición

**Inventario**
- Listado completo de productos con stock actualizado
- Agregar, editar y eliminar productos
- Visibilidad restringida según rol de usuario

**Clientes**
- Registro de clientes y seguimiento de saldo pendiente

**Pérdidas**
- Registro de pérdidas valoradas al costo de compra del producto

**Usuarios**
- Gestión de usuarios del sistema
- Dos roles: **Administrador** (acceso total) y **Empleado** (acceso restringido a ventas e inventario)

**Respaldo de datos**
- Exportación y copia de seguridad de la base de datos directamente a **Google Drive**

---

## 🗄️ Base de datos

- Motor: **SQLite**
- Estructura relacional con tablas para ventas, detalle de ventas, compras, inventario, clientes, pérdidas y usuarios
- Respaldo automático en la nube mediante integración con Google Drive

---

## 🔐 Sistema de autenticación

El sistema requiere usuario y contraseña para acceder. Los permisos se aplican dinámicamente según el rol:

| Funcionalidad | Empleado | Administrador |
|---|---|---|
| Registrar ventas | ✅ | ✅ |
| Ver inventario | ✅ | ✅ |
| Ver clientes | ✅ | ✅ |
| Registrar compras | ❌ | ✅ |
| Registrar pérdidas | ❌ | ✅ |
| Gestionar usuarios | ❌ | ✅ |
| Respaldo Google Drive | ❌ | ✅ |

---

## 🛠️ Tecnologías utilizadas

- Python 3
- SQLite
- Tkinter (interfaz gráfica)
- Google Drive API (respaldo en la nube)

---

## 👤 Autor

Samir Centeno — [@scentenoo](https://github.com/scentenoo)  
Estudiante de Estadística — Universidad Nacional de Colombia, Sede Medellín
