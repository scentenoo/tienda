# 🛒 Sistema de Gestión Comercial

Sistema de escritorio para la gestión integral de un negocio comercial, desarrollado en Python con base de datos SQLite. Actualmente en uso activo en producción.

---

## 📌 Descripción

Aplicación de escritorio con interfaz gráfica que centraliza las operaciones de un negocio: ventas, compras, inventario, clientes y control de pérdidas. Implementa autenticación con roles diferenciados y respaldo automático de la base de datos en Google Drive.

---

## 🏗️ Arquitectura

El proyecto sigue el patrón **MVC (Modelo-Vista-Controlador)**:

```
tienda/
├── models/         → Acceso y lógica de datos (SQLite)
├── views/          → Interfaz gráfica (Tkinter)
├── controllers/    → Lógica de negocio
├── utils/          → Utilidades generales
├── config/         → Configuración del sistema
├── assets/         → Recursos visuales
└── data/           → Base de datos SQLite
```

---

## ⚙️ Funcionalidades

**Ventas**
- Registro detallado con fecha, hora y productos vendidos
- Asociación a clientes registrados o venta al contado
- Historial completo de transacciones

**Compras**
- Registro de compras con soporte para flete e IVA
- Control de costos de adquisición

**Inventario**
- Listado de productos con stock actualizado
- Agregar, editar y eliminar productos
- Visibilidad restringida según rol de usuario

**Clientes**
- Registro de clientes y seguimiento de saldo pendiente

**Pérdidas**
- Registro de pérdidas valoradas al costo de compra del producto

**Usuarios**
- Gestión de usuarios del sistema
- Dos roles: **Administrador** (acceso total) y **Empleado** (acceso restringido)

---

## 🔐 Sistema de autenticación

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

## 💾 Sistema de respaldo

El módulo de backup realiza las siguientes operaciones de forma automática:

- **Exportación segura** usando la API nativa de SQLite (`sqlite3.backup`) para evitar bloqueos durante la copia
- **Verificación de integridad** mediante `PRAGMA integrity_check` antes de confirmar el backup
- **Sincronización con Google Drive** copiando la base de datos a la carpeta local de Drive (requiere Google Drive Desktop activo en el equipo)
- **Rotación automática** — mantiene los últimos 30 backups y elimina los más antiguos
- **Reintentos con backoff exponencial** para manejar archivos bloqueados por otros procesos
- **Logging completo** de todas las operaciones en archivo `.log`

---

## 🗄️ Base de datos

- Motor: **SQLite**
- Estructura relacional con tablas para ventas, detalle de ventas, compras, inventario, clientes, pérdidas y usuarios

---

## 🛠️ Tecnologías utilizadas

- Python 3
- SQLite
- Tkinter (interfaz gráfica)
- Google Drive Desktop (respaldo en la nube vía carpeta sincronizada)

---

## 👤 Autor

Samir Centeno — [@scentenoo](https://github.com/scentenoo)  
Estudiante de Estadística — Universidad Nacional de Colombia, Sede Medellín
