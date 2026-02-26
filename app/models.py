from flask_login import UserMixin
from .extensions import db

# 1. TABLAS MAESTRAS (CATÁLOGOS)
class TipoDocumento(db.Model):
    __tablename__ = 'tipo_documento'
    id_tipodocuemnto = db.Column(db.String(50), primary_key=True)
    tipo_documento = db.Column(db.String(100))

class NivelEducativo(db.Model):
    __tablename__ = 'nivel_educativo'
    id_nivel = db.Column(db.String(50), primary_key=True)
    Nivel = db.Column(db.String(100))

class Profesion(db.Model):
    __tablename__ = 'profesion'
    id_profesion = db.Column(db.String(50), primary_key=True)
    Profesion = db.Column(db.String(200))

class Eps(db.Model):
    __tablename__ = 'eps'
    EPS = db.Column(db.String(100), primary_key=True) # Clave primaria es texto

class FondoPensiones(db.Model):
    __tablename__ = 'fondo_pensiones'
    Fondo_Pensiones = db.Column(db.String(100), primary_key=True) # Clave primaria es texto

class MotivoRetiro(db.Model):
    __tablename__ = 'motivo_retiro'
    Tipo_Retiro = db.Column(db.String(100), primary_key=True)

# 3. ROLES Y PERMISOS (NUEVO)
class Rol(db.Model):
    __tablename__ = 'rol'
    id_rol = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_rol = db.Column(db.String(50), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))

class Permiso(db.Model):
    __tablename__ = 'permiso'
    id_permiso = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre_permiso = db.Column(db.String(100), unique=True, nullable=False)
    descripcion = db.Column(db.String(200))

# 2. ESTRUCTURA ORGANIZACIONAL
class Departamento(db.Model):
    __tablename__ = 'departamento'
    Departamento = db.Column(db.String(100), primary_key=True)
    Presupuestados = db.Column(db.Integer, default=0)

class Area(db.Model):
    __tablename__ = 'area'
    Area = db.Column(db.String(100), primary_key=True)
    Departamento = db.Column(db.String(100), db.ForeignKey('departamento.Departamento'))
    Presupuestados = db.Column(db.Integer, default=0)
    departamento_rel = db.relationship('Departamento', backref='areas')

class PerfilOcupacional(db.Model):
    __tablename__ = 'perfil_ocupacional'
    ID_Perfil_Ocupacional = db.Column(db.String(50), primary_key=True)
    Perfil_Ocupacional = db.Column(db.String(150))
    Area = db.Column(db.String(100), db.ForeignKey('area.Area'))
    area_rel = db.relationship('Area', backref='perfiles')
    Presupuestados = db.Column(db.Integer, default=0)

# 3. TABLA CENTRAL: EMPLEADO
class Empleado(db.Model, UserMixin):
    __tablename__ = 'empleado'
    ID_Cedula = db.Column(db.String(50), primary_key=True)
    id_tipodocuemnto = db.Column(db.String(50), db.ForeignKey('tipo_documento.id_tipodocuemnto'))
    Nombre_Completo = db.Column(db.String(250), nullable=False)
    Fecha_Ingreso = db.Column(db.Date, nullable=False) # En SQL es DATE
    Fecha_Nacimiento = db.Column(db.Date, nullable=True) # Para módulo de cumpleaños
    
    id_profesion = db.Column(db.String(50), db.ForeignKey('profesion.id_profesion'))
    id_nivel = db.Column(db.String(50), db.ForeignKey('nivel_educativo.id_nivel'))
    ID_Perfil_Ocupacional = db.Column(db.String(50), db.ForeignKey('perfil_ocupacional.ID_Perfil_Ocupacional'))
    EPS_Actual = db.Column(db.String(100), db.ForeignKey('eps.EPS'))
    Fondo_Actual = db.Column(db.String(100), db.ForeignKey('fondo_pensiones.Fondo_Pensiones'))
    Salario_Base = db.Column(db.Numeric(10, 2), default=0.00)
    Correo_Electronico = db.Column(db.String(150), nullable=True)
    Telefono = db.Column(db.String(50), nullable=True) # Nuevo campo para el teléfono
    Celular = db.Column(db.String(20), nullable=True)
    Sexo = db.Column(db.String(1), nullable=True)
    Contacto_Emergencia = db.Column(db.String(250), nullable=True)
    Telefono_Contacto = db.Column(db.String(20), nullable=True)
    
    # Campos nuevos o modificados según tu SQL
    id_rol = db.Column(db.Integer, db.ForeignKey('rol.id_rol'))
    Imagen_Perfil = db.Column(db.String(255))
    Archivo_Soporte = db.Column(db.String(255), nullable=True)
    Estado_Laboral = db.Column(db.String(20), default='Activo')
    
    # NOTA: Contrasena no estaba en tu SQL CREATE TABLE, pero es obligatoria para el login.
    # Se mantendrá aquí y el script de inicialización la creará si falta.
    Contrasena = db.Column(db.String(255)) 

    # Relaciones (Backrefs útiles para el Dashboard y Perfil)
    eps_rel = db.relationship('Eps', backref='empleados')
    fondo_rel = db.relationship('FondoPensiones', backref='empleados')
    profesion_rel = db.relationship('Profesion', backref='empleados')
    perfil_rel = db.relationship('PerfilOcupacional', backref='empleados')
    rol_rel = db.relationship('Rol', backref='empleados')

    def get_id(self):
        return self.ID_Cedula

    @property
    def is_active(self):
        """Sobrescribe la propiedad de Flask-Login para bloquear usuarios inactivos"""
        return self.Estado_Laboral == 'Activo'

# 4. DATOS FAMILIARES
class Hijos(db.Model):
    __tablename__ = 'hijos'
    ID_Hijo = db.Column(db.String(50), primary_key=True)
    ID_Cedula = db.Column(db.String(50), db.ForeignKey('empleado.ID_Cedula'))
    Identificacion_Hijo = db.Column(db.String(50))
    Apellidos_Nombre = db.Column(db.String(250))
    Fecha_Nacimiento = db.Column(db.Date, nullable=True)
    Sexo = db.Column(db.String(1))
    Estado = db.Column(db.String(20))

class Reunion(db.Model):
    __tablename__ = 'reunion'
    id = db.Column(db.Integer, primary_key=True)
    ID_Cedula = db.Column(db.String(50), db.ForeignKey('empleado.ID_Cedula'))
    Titulo = db.Column(db.String(200))
    Fecha_Hora = db.Column(db.DateTime, nullable=False)

class PagoNomina(db.Model):
    __tablename__ = 'pago_nomina'
    id = db.Column(db.Integer, primary_key=True)
    ID_Cedula = db.Column(db.String(50), db.ForeignKey('empleado.ID_Cedula'))
    Fecha_Pago = db.Column(db.Date, nullable=False)
    Mes = db.Column(db.String(20))
    Ano = db.Column(db.Integer)
    Salario_Base = db.Column(db.Numeric(10, 2))
    Aux_Transporte = db.Column(db.Numeric(10, 2))
    Deducciones_Salud = db.Column(db.Numeric(10, 2))
    Deducciones_Pension = db.Column(db.Numeric(10, 2))
    Total_Devengado = db.Column(db.Numeric(10, 2))
    Total_Deducido = db.Column(db.Numeric(10, 2))
    Neto_Pagar = db.Column(db.Numeric(10, 2))
    Estado = db.Column(db.String(20), default='Pagado')