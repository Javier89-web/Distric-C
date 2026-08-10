from django.db import models
from django.utils import timezone
from django.conf import settings
from decimal import Decimal

class Usuario(models.Model):
    id_usuario = models.AutoField(primary_key=True)
    cedula_usuario = models.CharField(
        max_length=10,
        unique=True,
        null=True,
        blank=True
    )
    nombre_usuario = models.CharField(max_length=100)
    apellido_usuario = models.CharField(max_length=100)
    correo_usuario = models.EmailField(unique=True)
    telefono_usuario = models.CharField(
        max_length=15,
        null=True,
        blank=True
    )
    contrasena_usuario = models.CharField(max_length=128)
    foto_usuario = models.ImageField(
        upload_to='usuarios/',
        blank=True,
        null=True
    )
    tiporol = models.CharField(
        max_length=20,
        choices=[
            ('USUARIO', 'USUARIO'),
            ('ADMINISTRADOR', 'ADMINISTRADOR')
        ]
    )
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre_usuario} {self.apellido_usuario}"


class Administrador(models.Model):
    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE)#tabla Administrador con relación OneToOne (1 a 1)
    cargo = models.CharField(max_length=100, null=True, blank=True)
    codigo_interno = models.CharField(max_length=50, unique=True, null=True, blank=True)
    telefono_institucional = models.CharField(max_length=20, null=True, blank=True)



class ChecklistVehiculo(models.Model):
    id_checklist = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="checklists")
    creado_en = models.DateTimeField(default=timezone.now)
    SI_NO = (('SI', 'Si'), ('NO', 'No'))
    # Documentos indispensables
    licencia_conducir = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    tarjeta_circulacion = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    poliza_impresa = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    poliza_digital = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    verificacion_vehicular = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    factura_propiedad = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)

    # Chequeo mecánico esencial
    llantas = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    frenos = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    luces = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    fluidos_aceite = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    fluido_agua = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    bateria_general = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    cinturones = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    limpiaparabrisas = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)

    # Estado general del motor
    motor_aceite = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    motor_refrigerante = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    motor_temperatura = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    motor_bateria = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    motor_filtro_aire = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    motor_fugas = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    motor_combustible = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)

    # Suspensión / transmisión
    amortiguadores = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    alineacion = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    soportes_motor = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    caja = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    embrague = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)

    # Equipo de seguridad requerido
    triangulo = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    chaleco = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    extintor = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    gato_llave = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    botiquin = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    linterna = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    cables_corriente = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    tacos_ruedas = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)
    llanta_reparacion = models.CharField(max_length=2, choices=SI_NO, null=True, blank=True)

    def __str__(self):
        return f"Checklist #{self.id_checklist} - {self.usuario.nombre_usuario} ({self.creado_en.date()})"



class Vehiculo(models.Model):

    TIPOS_VEHICULO = [
        ('AUTOMOVIL', 'AUTOMÓVIL'),
        ('TAXI', 'TAXI'),
        ('MOTOCICLETA', 'MOTOCICLETA'),
        ('CAMION', 'CAMIÓN'),
        ('CAMIONETA', 'CAMIONETA'),
    ]

    TIPOS_COMBUSTIBLE = [
        ('EXTRA', 'EXTRA'),
        ('DIESEL', 'DIÉSEL'),
        ('SUPER', 'SÚPER'),
        ('ECOPAIS', 'ECOPAÍS'),
    ]

    id_vehiculo = models.AutoField(
        primary_key=True
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name="vehiculos",
        null=True,
        blank=True
    )

    tipovehiculo_vehiculo = models.CharField(
        max_length=50,
        choices=TIPOS_VEHICULO
    )

    tipocombustible_vehiculo = models.CharField(
        max_length=50,
        choices=TIPOS_COMBUSTIBLE
    )

    matricula_vehiculo = models.CharField(
        max_length=100,
        unique=True
    )

    modelo_vehiculo = models.CharField(
        max_length=50,
        blank=True
    )

    foto_vehiculo = models.ImageField(
        upload_to='vehiculos/',
        blank=True,
        null=True
    )

    numero_cedula = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    numero_motor = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    numero_chasis = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True
    )

    peso_auto = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True
    )

    capacidad_carga_kg = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        blank=True,
        null=True
    )

    cilindraje = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        blank=True,
        null=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"],
                name="un_vehiculo_por_usuario"
            )
        ]

    def __str__(self):
        modelo = self.modelo_vehiculo or "Sin modelo"

        return (
            f"{self.matricula_vehiculo} - "
            f"{modelo}"
        )



class CargaVehiculo(models.Model):
    id_carga = models.AutoField(primary_key=True)
    vehiculo = models.ForeignKey(Vehiculo,on_delete=models.CASCADE,related_name="cargas")
    nombre_producto = models.CharField(max_length=100)
    # peso en toneladas o en kg, según lo que decidas usar
    peso_adicional = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.nombre_producto} - {self.peso_adicional} kg"



class ProductoCarga(models.Model):

    PRESENTACIONES = [
        ('GALON', 'GALÓN'),
        ('JABA', 'JABA'),
        ('PAQUETE', 'PAQUETE'),
        ('BOTELLA', 'BOTELLA'),
        ('CAJA', 'CAJA'),
        ('FUNDA', 'FUNDA'),
        ('UNIDAD', 'UNIDAD'),
    ]

    id_producto_carga = models.AutoField(
        primary_key=True
    )

    codigo_catalogo = models.CharField(
        max_length=20,
        blank=True,
        default=''
    )

    nombre_producto = models.CharField(
        max_length=100
    )

    marca_producto = models.CharField(
        max_length=100,
        blank=True
    )

    precio_referencia = models.DecimalField(
        max_digits=9,
        decimal_places=2,
        null=True,
        blank=True
    )

    presentacion_producto = models.CharField(
        max_length=20,
        choices=PRESENTACIONES
    )

    nota_producto = models.CharField(
        max_length=250,
        blank=True
    )

    peso_unitario_kg = models.DecimalField(
        max_digits=9,
        decimal_places=2
    )

    activo = models.BooleanField(
        default=True
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            'nombre_producto',
            'marca_producto',
            'presentacion_producto'
        ]

    @property
    def unidad_carga(self):
        return self.get_presentacion_producto_display().lower()

    @property
    def unidad_carga_plural(self):
        plurales = {
            "GALON": "galones",
            "JABA": "jabas",
            "PAQUETE": "paquetes",
            "BOTELLA": "botellas",
            "CAJA": "cajas",
            "FUNDA": "fundas",
            "UNIDAD": "unidades",
        }
        return plurales.get(self.presentacion_producto, f"{self.unidad_carga}s")

    @property
    def presentacion_descriptiva(self):
        return f"{self.get_presentacion_producto_display().title()} de {self.nombre_producto}"

    def __str__(self):
        marca = (
            f" - {self.marca_producto}"
            if self.marca_producto
            else ""
        )

        return (
            f"{self.nombre_producto}{marca} "
            f"({self.get_presentacion_producto_display()})"
        )


class PlanCarga(models.Model):

    ESTADOS = [
        ('BORRADOR', 'BORRADOR'),
        ('LISTO', 'LISTO'),
        ('CONFIRMADO', 'CONFIRMADO'),
        ('EN_RUTA', 'EN RUTA'),
        ('COMPLETADO', 'COMPLETADO'),
        ('CANCELADO', 'CANCELADO'),
    ]

    id_plan_carga = models.AutoField(
        primary_key=True
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name='planes_carga'
    )

    fecha_planificada = models.DateField()

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='BORRADOR'
    )

    notas = models.TextField(
        blank=True
    )

    creado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name='planes_carga_creados',
        null=True,
        blank=True
    )

    revisado_por_usuario = models.BooleanField(
        default=False
    )

    fecha_revision_usuario = models.DateTimeField(
        null=True,
        blank=True
    )

    ajustado_por_usuario = models.BooleanField(
        default=False
    )

    fecha_ultimo_ajuste_usuario = models.DateTimeField(
        null=True,
        blank=True
    )

    confirmado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name='planes_carga_confirmados',
        null=True,
        blank=True
    )

    fecha_confirmacion = models.DateTimeField(
        null=True,
        blank=True
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    fecha_actualizacion = models.DateTimeField(
        auto_now=True
    )

    class Meta:
        ordering = [
            '-fecha_planificada',
            'vehiculo__matricula_vehiculo'
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'vehiculo',
                    'fecha_planificada'
                ],
                name='un_plan_carga_por_vehiculo_fecha'
            )
        ]

    @property
    def peso_programado_kg(self):
        return sum(
            (
                detalle.peso_subtotal_kg or Decimal('0.00')
                for detalle in self.detalles.all()
            ),
            Decimal('0.00')
        )

    @property
    def peso_total_kg(self):
        """Peso efectivo que realmente saldrá en el vehículo."""
        return sum(
            (
                detalle.peso_actual_kg or Decimal('0.00')
                for detalle in self.detalles.all()
            ),
            Decimal('0.00')
        )

    @property
    def peso_descartado_kg(self):
        return sum(
            (
                detalle.peso_descartado_kg
                for detalle in self.detalles.all()
            ),
            Decimal('0.00')
        )

    @property
    def peso_agregado_usuario_kg(self):
        return sum(
            (
                detalle.peso_actual_kg or Decimal('0.00')
                for detalle in self.detalles.all()
                if detalle.origen == 'USUARIO'
            ),
            Decimal('0.00')
        )

    @property
    def capacidad_kg(self):
        return (
            self.vehiculo.capacidad_carga_kg
            or Decimal('0.00')
        )

    @property
    def disponible_kg(self):
        disponible = (
            self.capacidad_kg -
            self.peso_total_kg
        )

        return max(
            disponible,
            Decimal('0.00')
        )

    @property
    def porcentaje_carga(self):
        if self.capacidad_kg <= 0:
            return Decimal('0.00')

        porcentaje = (
            self.peso_total_kg /
            self.capacidad_kg
        ) * Decimal('100')

        return min(
            porcentaje,
            Decimal('100.00')
        )

    @property
    def peso_asignado_paradas_kg(self):
        return sum(
            (
                entrega.peso_actual_kg or Decimal('0.00')
                for parada in self.paradas.all()
                for entrega in parada.entregas.all()
            ),
            Decimal('0.00')
        )

    @property
    def peso_sin_destino_kg(self):
        pendiente = (
            self.peso_total_kg -
            self.peso_asignado_paradas_kg
        )

        return max(
            pendiente,
            Decimal('0.00')
        )

    @property
    def distribucion_completa(self):
        detalles = list(self.detalles.all())

        if not detalles or not self.paradas.exists():
            return False

        for detalle in detalles:
            cantidad_asignada = sum(
                entrega.cantidad_actual
                for entrega in detalle.entregas.all()
            )

            if cantidad_asignada != detalle.cantidad_actual:
                return False

        return True

    @property
    def permite_ajustes_usuario(self):
        return self.estado == 'LISTO'

    @property
    def permite_configuracion_admin(self):
        return self.estado == 'BORRADOR'

    def __str__(self):
        return (
            f"{self.vehiculo.matricula_vehiculo} - "
            f"{self.fecha_planificada}"
        )


class DetallePlanCarga(models.Model):

    ORIGENES = [
        ('ADMINISTRADOR', 'ADMINISTRADOR'),
        ('USUARIO', 'USUARIO'),
    ]

    id_detalle_plan_carga = models.AutoField(
        primary_key=True
    )

    plan = models.ForeignKey(
        PlanCarga,
        on_delete=models.CASCADE,
        related_name='detalles'
    )

    producto = models.ForeignKey(
        ProductoCarga,
        on_delete=models.PROTECT,
        related_name='detalles_plan'
    )

    # Cantidad originalmente asignada o agregada.
    cantidad = models.PositiveIntegerField()

    # Cantidad que realmente permanece dentro del vehículo.
    cantidad_actual = models.PositiveIntegerField(
        default=0
    )

    origen = models.CharField(
        max_length=20,
        choices=ORIGENES,
        default='ADMINISTRADOR'
    )

    agregado_por = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name='productos_carga_agregados',
        null=True,
        blank=True
    )

    fecha_agregado = models.DateTimeField(
        default=timezone.now
    )

    peso_unitario_kg = models.DecimalField(
        max_digits=9,
        decimal_places=2
    )

    # Peso original de este detalle.
    peso_subtotal_kg = models.DecimalField(
        max_digits=11,
        decimal_places=2
    )

    # Peso efectivo que se toma para la carga actual.
    peso_actual_kg = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        default=Decimal('0.00')
    )

    class Meta:
        ordering = [
            'producto__nombre_producto'
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'plan',
                    'producto'
                ],
                name='producto_unico_por_plan_carga'
            )
        ]

    @property
    def cantidad_descartada(self):
        return max(
            self.cantidad - self.cantidad_actual,
            0
        )

    @property
    def peso_descartado_kg(self):
        return (
            Decimal(self.cantidad_descartada) *
            self.peso_unitario_kg
        )

    @property
    def estado_ajuste(self):
        if self.cantidad_actual == 0:
            return 'DESCARTADO'

        if self.cantidad_actual != self.cantidad:
            return 'AJUSTADO'

        if self.origen == 'USUARIO':
            return 'AGREGADO POR USUARIO'

        return 'ACTIVO'

    @property
    def cantidad_asignada_paradas(self):
        return sum(
            entrega.cantidad_actual
            for entrega in self.entregas.all()
        )

    @property
    def cantidad_pendiente_asignar(self):
        return max(
            self.cantidad_actual -
            self.cantidad_asignada_paradas,
            0
        )

    def save(self, *args, **kwargs):
        self.peso_subtotal_kg = (
            Decimal(self.cantidad) *
            self.peso_unitario_kg
        )

        self.peso_actual_kg = (
            Decimal(self.cantidad_actual) *
            self.peso_unitario_kg
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.cantidad_actual} de {self.cantidad} x "
            f"{self.producto.nombre_producto}"
        )


class ParadaPlanCarga(models.Model):

    id_parada_plan_carga = models.AutoField(
        primary_key=True
    )

    plan = models.ForeignKey(
        PlanCarga,
        on_delete=models.CASCADE,
        related_name='paradas'
    )

    nombre_parada = models.CharField(
        max_length=150
    )

    direccion_parada = models.CharField(
        max_length=250
    )

    latitud = models.DecimalField(
        max_digits=10,
        decimal_places=7
    )

    longitud = models.DecimalField(
        max_digits=10,
        decimal_places=7
    )

    orden = models.PositiveIntegerField()

    observaciones = models.CharField(
        max_length=250,
        blank=True
    )

    fecha_creacion = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            'orden',
            'id_parada_plan_carga'
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'plan',
                    'orden'
                ],
                name='orden_unico_por_plan_carga'
            )
        ]

    @property
    def peso_entrega_kg(self):
        return sum(
            (
                entrega.peso_actual_kg or Decimal('0.00')
                for entrega in self.entregas.all()
            ),
            Decimal('0.00')
        )

    @property
    def cantidad_unidades(self):
        return sum(
            entrega.cantidad_actual
            for entrega in self.entregas.all()
        )

    def __str__(self):
        return (
            f"{self.orden}. {self.nombre_parada} - "
            f"{self.plan}"
        )


class EntregaPlanCarga(models.Model):

    id_entrega_plan_carga = models.AutoField(
        primary_key=True
    )

    parada = models.ForeignKey(
        ParadaPlanCarga,
        on_delete=models.CASCADE,
        related_name='entregas'
    )

    detalle = models.ForeignKey(
        DetallePlanCarga,
        on_delete=models.CASCADE,
        related_name='entregas'
    )

    cantidad_asignada = models.PositiveIntegerField()

    cantidad_actual = models.PositiveIntegerField(
        default=0
    )

    peso_unitario_kg = models.DecimalField(
        max_digits=9,
        decimal_places=2
    )

    peso_asignado_kg = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        default=Decimal('0.00')
    )

    peso_actual_kg = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        default=Decimal('0.00')
    )

    class Meta:
        ordering = [
            'parada__orden',
            'detalle__producto__nombre_producto'
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    'parada',
                    'detalle'
                ],
                name='producto_unico_por_parada_carga'
            )
        ]

    @property
    def cantidad_descartada(self):
        return max(
            self.cantidad_asignada -
            self.cantidad_actual,
            0
        )

    @property
    def estado_ajuste(self):
        if self.cantidad_actual == 0:
            return 'DESCARTADO'

        if self.cantidad_actual < self.cantidad_asignada:
            return 'AJUSTADO'

        return 'ACTIVO'

    def save(self, *args, **kwargs):
        self.peso_unitario_kg = (
            self.detalle.peso_unitario_kg
        )

        self.peso_asignado_kg = (
            Decimal(self.cantidad_asignada) *
            self.peso_unitario_kg
        )

        self.peso_actual_kg = (
            Decimal(self.cantidad_actual) *
            self.peso_unitario_kg
        )

        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.cantidad_actual} x "
            f"{self.detalle.producto.nombre_producto} "
            f"en {self.parada.nombre_parada}"
        )


class AjusteCargaUsuario(models.Model):

    TIPOS_AJUSTE = [
        ('AGREGAR', 'PRODUCTO AGREGADO'),
        ('AJUSTAR', 'CANTIDAD AJUSTADA'),
        ('DESCARTAR', 'PRODUCTO DESCARTADO'),
        ('RESTAURAR', 'PRODUCTO RESTAURADO'),
    ]

    id_ajuste_carga = models.AutoField(
        primary_key=True
    )

    plan = models.ForeignKey(
        PlanCarga,
        on_delete=models.CASCADE,
        related_name='ajustes_usuario'
    )

    detalle = models.ForeignKey(
        DetallePlanCarga,
        on_delete=models.SET_NULL,
        related_name='ajustes_usuario',
        null=True,
        blank=True
    )

    entrega = models.ForeignKey(
        EntregaPlanCarga,
        on_delete=models.SET_NULL,
        related_name='ajustes_usuario',
        null=True,
        blank=True
    )

    parada = models.ForeignKey(
        ParadaPlanCarga,
        on_delete=models.SET_NULL,
        related_name='ajustes_usuario',
        null=True,
        blank=True
    )

    parada_nombre = models.CharField(
        max_length=150,
        blank=True
    )

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        related_name='ajustes_carga_realizados',
        null=True,
        blank=True
    )

    tipo_ajuste = models.CharField(
        max_length=20,
        choices=TIPOS_AJUSTE
    )

    producto_nombre = models.CharField(
        max_length=200
    )

    cantidad_anterior = models.PositiveIntegerField(
        default=0
    )

    cantidad_nueva = models.PositiveIntegerField(
        default=0
    )

    peso_anterior_kg = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        default=Decimal('0.00')
    )

    peso_nuevo_kg = models.DecimalField(
        max_digits=11,
        decimal_places=2,
        default=Decimal('0.00')
    )

    motivo = models.CharField(
        max_length=250
    )

    fecha_ajuste = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        ordering = [
            '-fecha_ajuste'
        ]

    @property
    def diferencia_peso_kg(self):
        return (
            self.peso_nuevo_kg -
            self.peso_anterior_kg
        )

    def __str__(self):
        return (
            f"{self.get_tipo_ajuste_display()} - "
            f"{self.producto_nombre}"
        )


#punto de inicio
class UbicacionVehiculo(models.Model):
    id_ubicacion=models.AutoField(primary_key=True)
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE, related_name="UbicacionVehiculos")
    latitud = models.FloatField()
    longitud = models.FloatField()
    fecha_hora = models.DateTimeField(default=timezone.now)


    def __str__(self):
        return f"{self.latitud}, {self.longitud} ({self.fecha_hora})"


#punto final
class Lugarguardado(models.Model):
    id_Lugarguardado=models.AutoField(primary_key=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="Lugarguardados")
    nombre_Lugarguardado = models.CharField(max_length=900) 
    latitud_Lugarguardado = models.FloatField()
    longitud_Lugarguardado = models.FloatField()
    fecha_guardado = models.DateTimeField(default=timezone.now)

    def __str__(self):
            return f"{self.nombre_Lugarguardado} ({self.latitud_Lugarguardado}, {self.longitud_Lugarguardado})"





class NodoMapa(models.Model):
    id_nodo = models.BigIntegerField(primary_key=True)
    nombre = models.CharField(max_length=200)  
    latitud = models.FloatField()
    longitud = models.FloatField()
    tipo = models.CharField(
        max_length=50,
        choices=[
            ('INTERSECCION', 'Intersección'),
            ('PUNTO_INTERES', 'Punto de interés'),
            ('PARROQUIA', 'Parroquia'),
        ],
        default='INTERSECCION'
    )

    def __str__(self):
        return self.nombre



class TramoVial(models.Model):
    id_tramo = models.AutoField(primary_key=True)
    origen = models.ForeignKey(NodoMapa, on_delete=models.CASCADE, related_name='tramos_salida')
    destino = models.ForeignKey(NodoMapa, on_delete=models.CASCADE, related_name='tramos_llegada')
    distancia_km = models.FloatField()
    tiempo_base_min = models.FloatField()
    tipo_via = models.CharField(
        max_length=50,
        choices=[
            ('URBANA', 'Urbana'),
            ('RURAL', 'Rural'),
            ('PRINCIPAL', 'Principal'),
            ('SECUNDARIA', 'Secundaria'),
        ],
        blank=True
    )

    # NUEVO: guarda la forma real del tramo de calle desde OSMnx
    geometria = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"{self.origen} -> {self.destino}"



# me permite guardar en la navegacion origen- destino
class Viaje(models.Model):
    ESTADOS = [
        ('PLANIFICADO', 'PLANIFICADO'),
        ('EN_RUTA', 'EN RUTA'),
        ('COMPLETADO', 'COMPLETADO'),
        ('CANCELADO', 'CANCELADO'),
    ]

    id_viaje = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name="viajes"
    )
    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.CASCADE,
        related_name="viajes"
    )
    origen = models.ForeignKey(
        UbicacionVehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='viajes_origen'
    )
    destino = models.ForeignKey(
        Lugarguardado,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='viajes_destino'
    )
    plan_carga = models.ForeignKey(
        PlanCarga,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='viajes'
    )
    es_prueba_administrativa = models.BooleanField(default=False)
    administrador_ejecutor = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pruebas_ruta_ejecutadas'
    )
    carga_prueba_snapshot = models.JSONField(default=list, blank=True)
    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default='PLANIFICADO'
    )

    origen_nombre = models.CharField(max_length=250, blank=True)
    origen_latitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    origen_longitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    destino_final_nombre = models.CharField(max_length=250, blank=True)
    destino_final_latitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    destino_final_longitud = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    carga_inicial_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    carga_final_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    distancia_estimada_total_km = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    distancia_real_total_km = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    tiempo_estimado_total_min = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    tiempo_real_total_min = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    consumo_estimado_total_l = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    consumo_real_total_l = models.DecimalField(max_digits=11, decimal_places=3, null=True, blank=True)
    costo_estimado_total = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    costo_real_total = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(default=timezone.now)
    notas_cierre = models.TextField(blank=True)

    class Meta:
        ordering = ['-fecha_creacion']

    @property
    def peso_carga_prueba_kg(self):
        total = Decimal('0.00')
        for item in self.carga_prueba_snapshot or []:
            try:
                total += Decimal(str(item.get('cantidad_actual', 0))) * Decimal(str(item.get('peso_unitario_kg', 0)))
            except (TypeError, ValueError, ArithmeticError):
                continue
        return total

    @property
    def numero_tramos(self):
        return self.tramos.count()

    @property
    def tramos_completados(self):
        return self.tramos.filter(estado='COMPLETADO').count()

    def recalcular_totales(self):
        tramos = self.tramos.filter(estado='COMPLETADO')
        self.distancia_estimada_total_km = sum(
            (tramo.distancia_estimada_km for tramo in tramos),
            Decimal('0.000')
        )
        self.distancia_real_total_km = sum(
            (tramo.distancia_real_km for tramo in tramos),
            Decimal('0.000')
        )
        self.tiempo_estimado_total_min = sum(
            (tramo.tiempo_estimado_min for tramo in tramos),
            Decimal('0.00')
        )
        self.tiempo_real_total_min = sum(
            (tramo.tiempo_real_min for tramo in tramos),
            Decimal('0.00')
        )
        self.consumo_estimado_total_l = sum(
            (tramo.consumo_estimado_l for tramo in tramos),
            Decimal('0.000')
        )
        consumos_reales = [
            tramo.consumo_real_l
            for tramo in tramos
            if tramo.consumo_real_l is not None
        ]
        self.consumo_real_total_l = (
            sum(consumos_reales, Decimal('0.000'))
            if consumos_reales else None
        )
        self.costo_estimado_total = sum(
            (tramo.costo_estimado for tramo in tramos),
            Decimal('0.00')
        )
        costos_reales = [
            tramo.costo_real
            for tramo in tramos
            if tramo.costo_real is not None
        ]
        self.costo_real_total = (
            sum(costos_reales, Decimal('0.00'))
            if costos_reales else None
        )
        ultimo = tramos.order_by('-orden').first()
        if ultimo:
            self.carga_final_kg = ultimo.carga_restante_kg
        self.save(update_fields=[
            'distancia_estimada_total_km',
            'distancia_real_total_km',
            'tiempo_estimado_total_min',
            'tiempo_real_total_min',
            'consumo_estimado_total_l',
            'consumo_real_total_l',
            'costo_estimado_total',
            'costo_real_total',
            'carga_final_kg',
        ])

    def __str__(self):
        return f"Viaje {self.id_viaje} - {self.usuario.nombre_usuario}"


class TramoViaje(models.Model):
    ESTADOS = [
        ('PLANIFICADO', 'PLANIFICADO'),
        ('PREPARADO', 'PREPARADO'),
        ('EN_RUTA', 'EN RUTA'),
        ('PAUSADO', 'PAUSADO'),
        ('COMPLETADO', 'COMPLETADO'),
        ('CANCELADO', 'CANCELADO'),
    ]

    id_tramo_viaje = models.AutoField(primary_key=True)
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name='tramos')
    orden = models.PositiveIntegerField()
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PLANIFICADO')

    origen_nombre = models.CharField(max_length=250)
    origen_latitud = models.DecimalField(max_digits=10, decimal_places=7)
    origen_longitud = models.DecimalField(max_digits=10, decimal_places=7)
    destino_nombre = models.CharField(max_length=250)
    destino_latitud = models.DecimalField(max_digits=10, decimal_places=7)
    destino_longitud = models.DecimalField(max_digits=10, decimal_places=7)

    ruta_seleccionada = models.ForeignKey(
        'RutaOpcion',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seleccionada_en_tramos'
    )

    carga_inicio_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    peso_entregado_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    carga_restante_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))

    distancia_estimada_km = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    distancia_real_km = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    tiempo_estimado_min = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    tiempo_real_min = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    consumo_base_l = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    consumo_estimado_l = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    consumo_real_l = models.DecimalField(max_digits=11, decimal_places=3, null=True, blank=True)
    costo_estimado = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    costo_real = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)

    trafico_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    trafico_descripcion = models.CharField(max_length=100, blank=True)
    clima_factor = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('1.00'))
    clima_descripcion = models.CharField(max_length=150, blank=True)
    temperatura_c = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    modelo_ia = models.CharField(max_length=120, blank=True)
    detalle_prediccion = models.JSONField(default=dict, blank=True)
    geometria_ruta = models.JSONField(default=list, blank=True)

    fecha_inicio = models.DateTimeField(null=True, blank=True)
    fecha_fin = models.DateTimeField(null=True, blank=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    nota_finalizacion = models.TextField(blank=True)
    evidencia_entrega = models.ImageField(
        upload_to='evidencias_entrega/%Y/%m/',
        blank=True,
        null=True
    )

    class Meta:
        ordering = ['orden']
        constraints = [
            models.UniqueConstraint(
                fields=['viaje', 'orden'],
                name='orden_unico_tramo_por_viaje'
            )
        ]

    @property
    def duracion_actual_min(self):
        if not self.fecha_inicio:
            return Decimal('0.00')
        fin = self.fecha_fin or timezone.now()
        segundos = max((fin - self.fecha_inicio).total_seconds(), 0)
        return Decimal(str(round(segundos / 60, 2)))

    def __str__(self):
        return f"Tramo {self.orden}: {self.origen_nombre} -> {self.destino_nombre}"


class RutaOpcion(models.Model):
    TIPOS = [
        ('OPTIMA', 'ÓPTIMA'),
        ('RECOMENDADA', 'RECOMENDADA'),
        ('ALTERNATIVA', 'ALTERNATIVA'),
    ]

    id_ruta_opcion = models.AutoField(primary_key=True)
    viaje = models.ForeignKey(Viaje, on_delete=models.CASCADE, related_name="opciones")
    tramo = models.ForeignKey(
        TramoViaje,
        on_delete=models.CASCADE,
        related_name='opciones',
        null=True,
        blank=True
    )
    tipo = models.CharField(max_length=20, choices=TIPOS, default='ALTERNATIVA')
    indice_opcion = models.PositiveSmallIntegerField(default=1)
    es_recomendada = models.BooleanField(default=False)
    seleccionada = models.BooleanField(default=False)

    tiempo_min = models.FloatField()
    distancia_km = models.FloatField()
    consumo_litros = models.FloatField(null=True, blank=True)
    costo_estimado = models.FloatField(null=True, blank=True)
    combustible_tipo = models.CharField(
        max_length=20,
        choices=[
            ('EXTRA', 'EXTRA'),
            ('DIESEL', 'DIESEL'),
            ('SUPER', 'SUPER'),
            ('ECOPAIS', 'ECOPAIS')
        ],
        null=True,
        blank=True
    )

    geometria = models.JSONField(default=list, blank=True)
    fuente_ruta = models.CharField(max_length=80, default='Dijkstra + teoría de grafos')
    consumo_base_litros = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    consumo_predicho_litros = models.DecimalField(max_digits=11, decimal_places=3, default=Decimal('0.000'))
    carga_inicio_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    score_optimizacion = models.DecimalField(max_digits=12, decimal_places=5, default=Decimal('0.00000'))
    modelo_ia = models.CharField(max_length=120, blank=True)
    detalle_prediccion = models.JSONField(default=dict, blank=True)
    fecha_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['tramo__orden', 'indice_opcion']
        constraints = [
            models.UniqueConstraint(
                fields=['tramo', 'indice_opcion'],
                name='indice_unico_opcion_por_tramo'
            )
        ]

    def __str__(self):
        return f"Viaje {self.viaje.id_viaje} - opción {self.indice_opcion}"


class PuntoGPSViaje(models.Model):
    id_punto_gps = models.BigAutoField(primary_key=True)
    tramo = models.ForeignKey(TramoViaje, on_delete=models.CASCADE, related_name='puntos_gps')
    latitud = models.DecimalField(max_digits=10, decimal_places=7)
    longitud = models.DecimalField(max_digits=10, decimal_places=7)
    precision_m = models.DecimalField(max_digits=9, decimal_places=2, null=True, blank=True)
    velocidad_m_s = models.DecimalField(max_digits=9, decimal_places=3, null=True, blank=True)
    rumbo_grados = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    distancia_desde_anterior_m = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    distancia_destino_m = models.DecimalField(max_digits=11, decimal_places=2, null=True, blank=True)
    fecha_hora = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['fecha_hora']

    def __str__(self):
        return f"GPS tramo {self.tramo_id}: {self.latitud}, {self.longitud}"


class EntregaTramoViaje(models.Model):
    id_entrega_tramo = models.AutoField(primary_key=True)
    tramo = models.ForeignKey(TramoViaje, on_delete=models.CASCADE, related_name='entregas_realizadas')
    detalle_carga = models.ForeignKey(
        DetallePlanCarga,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='entregas_tramos'
    )
    producto_nombre = models.CharField(max_length=200)
    marca_producto = models.CharField(max_length=100, blank=True)
    presentacion_producto = models.CharField(max_length=40, blank=True)
    cantidad_entregada = models.PositiveIntegerField(default=0)
    peso_unitario_kg = models.DecimalField(max_digits=9, decimal_places=2)
    peso_entregado_kg = models.DecimalField(max_digits=11, decimal_places=2, default=Decimal('0.00'))
    fecha_entrega = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['producto_nombre']

    @property
    def unidad_carga(self):
        return (self.presentacion_producto or "unidad").lower()

    @property
    def unidad_carga_plural(self):
        plurales = {
            "galón": "galones",
            "jaba": "jabas",
            "paquete": "paquetes",
            "botella": "botellas",
            "caja": "cajas",
            "funda": "fundas",
            "unidad": "unidades",
        }
        return plurales.get(self.unidad_carga, f"{self.unidad_carga}s")

    @property
    def presentacion_descriptiva(self):
        return f"{(self.presentacion_producto or 'Unidad').title()} de {self.producto_nombre}"

    def save(self, *args, **kwargs):
        self.peso_entregado_kg = Decimal(self.cantidad_entregada) * self.peso_unitario_kg
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.cantidad_entregada} x {self.producto_nombre}"


class EventoAdmin(models.Model):
    id_evento = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=200)
    inicio_fecha = models.DateField()
    inicio_hora = models.TimeField()
    fin_fecha = models.DateField(null=True, blank=True)
    fin_hora = models.TimeField(null=True, blank=True)
    descripcion = models.TextField(blank=True)
    creado_por = models.ForeignKey('Administrador', on_delete=models.CASCADE)
    def __str__(self):
        return f"{self.titulo} ({self.inicio_fecha} {self.inicio_hora})"




class AsignacionEvento(models.Model):
    id_usuario_evento = models.AutoField(primary_key=True)
    descripcion_evento = models.TextField(blank=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    evento = models.ForeignKey(EventoAdmin, on_delete=models.CASCADE)
    fecha_asignacion = models.DateTimeField(null=True, blank=True)
    ESTADOS = (('PENDIENTE', 'PENDIENTE'),('COMPLETADO', 'COMPLETADO'),('ATRASADO', 'ATRASADO'),('NO COMPLETADO', 'NO COMPLETADO'),)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PENDIENTE')
    estado_fecha = models.DateTimeField(null=True, blank=True)  # cuándo cambió el estado
    motivo_atrasado = models.TextField(null=True, blank=True)
    motivo_no_completado = models.TextField(null=True, blank=True)
    
    class Meta:
        unique_together = ('usuario', 'evento')

    def __str__(self):
        return f"{self.usuario.nombre_usuario} asignado a {self.evento.titulo}"






class Proveedor(models.Model):
    id_proveedor = models.AutoField(primary_key=True)
    nombre_proveedor = models.CharField(max_length=150)
    direccion_proveedor = models.CharField(max_length=255, blank=True, null=True)
    telefono_proveedor = models.CharField(max_length=20, blank=True, null=True)
    correo_proveedor = models.EmailField(unique=True)
    ruc_proveedor = models.CharField(max_length=13, unique=True)
    estado_proveedor = models.CharField(max_length=20, choices=[('ACTIVO', 'ACTIVO'),('INACTIVO', 'INACTIVO')])






class Pedido(models.Model):
    id_pedido = models.AutoField(primary_key=True)
    descripcion_pedido = models.TextField(blank=True, null=True)
    proveedor = models.ForeignKey(Proveedor, on_delete=models.SET_NULL, null=True, blank=True)
    evento = models.ForeignKey(EventoAdmin, on_delete=models.SET_NULL, null=True, blank=True)  # Viaje
    fecha_pedido = models.DateField()
    estado_pedido = models.CharField(max_length=20, choices=[('PENDIENTE', 'PENDIENTE'),('EN PROCESO', 'EN PROCESO'),('ENTREGADO', 'ENTREGADO'),('CANCELADO', 'CANCELADO')])



   

class DetallePedido(models.Model):
    id_detalle_pedido = models.AutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido,on_delete=models.CASCADE)
    descripcion_item = models.CharField(max_length=255)
    cantidad = models.PositiveIntegerField()
    precio_unitario = models.DecimalField(max_digits=10,decimal_places=2,default=0)

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.descripcion_item} - Pedido #{self.pedido.id_pedido}"




class Factura(models.Model):
    id_factura = models.AutoField(primary_key=True)
    cliente_nombre = models.CharField(max_length=150)
    numero_factura = models.CharField(max_length=30,unique=True,help_text="Ej: 001-001-000000123")
    fecha_emision = models.DateTimeField(default=timezone.now)
    pedido = models.ForeignKey(Pedido,on_delete=models.SET_NULL,null=True,blank=True)
    numero_cuenta = models.CharField(max_length=30,blank=True,null=True)
    # Totales contables (CIERRE)
    subtotal = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))
    iva = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))
    total = models.DecimalField(max_digits=12,decimal_places=2,default=Decimal("0.00"))

    # Estado de la factura
    estado_factura = models.CharField(max_length=50,choices=[('PENDIENTE', 'PENDIENTE'),('PAGADA', 'PAGADA'),('ANULADA', 'ANULADA')],default='PENDIENTE')

    def __str__(self):
        return f"Factura #{self.numero_factura} - {self.cliente_nombre}"


    # Método contable (opcional)
    def recalcular_totales(self):
        """
        Recalcula los totales usando los detalles del pedido asociado.
        Se usa SOLO al crear la factura o bajo control administrativo.
        """
        if not self.pedido:
            return

        detalles = self.pedido.detallepedido_set.all()
        subtotal = Decimal("0.00")
        for d in detalles:
            subtotal += d.subtotal()

        iva = (subtotal * Decimal("0.15")).quantize(Decimal("0.01"))
        total = (subtotal + iva).quantize(Decimal("0.01"))

        self.subtotal = subtotal
        self.iva = iva
        self.total = total
        self.save()



class Pago(models.Model):
    id_pago = models.AutoField(primary_key=True)
    factura = models.ForeignKey(Factura,on_delete=models.CASCADE,related_name="pagos")
    metodo_pago = models.CharField(max_length=20,choices=[('EFECTIVO', 'EFECTIVO'),('TRANSFERENCIA', 'TRANSFERENCIA')])
    monto_pagado = models.DecimalField(max_digits=12,decimal_places=2)
    banco = models.CharField(max_length=50,blank=True,null=True)
    referencia = models.CharField(max_length=100,blank=True,null=True,help_text="N° transferencia, depósito, etc.")
    estado_pago = models.CharField(max_length=20,choices=[('PENDIENTE', 'PENDIENTE'),('CONFIRMADO', 'CONFIRMADO'),('RECHAZADO', 'RECHAZADO')],default='CONFIRMADO')
    comprobante = models.ImageField(upload_to='comprobantes/',blank=True,null=True)
    fecha_pago = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"Pago #{self.id_pago} - {self.factura.numero_factura} - {self.monto_pagado}"




class Salvoconducto(models.Model):
    id_salvoconducto = models.AutoField(primary_key=True)
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.CASCADE)
    viaje = models.OneToOneField(Viaje, on_delete=models.CASCADE)
    motivo = models.TextField()
    fecha_emision = models.DateTimeField(default=timezone.now)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField()
    estado = models.CharField(max_length=20,choices=[('VIGENTE', 'VIGENTE'),('VENCIDO', 'VENCIDO'),('ANULADO', 'ANULADO')],default='VIGENTE')
    codigo_qr = models.ImageField(upload_to='salvoconductos_qr/', blank=True, null=True)
    documento_pdf = models.FileField(upload_to='salvoconductos_pdf/', blank=True, null=True)


    def __str__(self):
        return f"Salvoconducto #{self.id_salvoconducto} - {self.vehiculo.matricula_vehiculo}"


    def estado_actual(self):
        """Estado calculado en tiempo real."""
        if self.estado == 'ANULADO':
            return 'ANULADO'
        if timezone.now().date() > self.fecha_fin:
            return 'VENCIDO'
        return 'VIGENTE'



#tablas extra
class PrecioCombustible(models.Model):
    TIPO_CHOICES = [('EXTRA', 'EXTRA'),('DIESEL', 'DIESEL'),('SUPER', 'SUPER'),('ECOPAIS', 'ECOPAIS'),]
    id_precio = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    precio_por_litro = models.FloatField()  

    def __str__(self):
        return f"{self.tipo} - {self.precio_por_litro} USD/L"



class HistorialPrecioCombustible(models.Model):
    UNIDAD_CHOICES = [
        ('LITRO', 'Litro'),
        ('GALON', 'Galón'),
    ]

    id_historial_precio = models.AutoField(primary_key=True)
    tipo = models.CharField(max_length=20, choices=PrecioCombustible.TIPO_CHOICES)
    precio_anterior_litro = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True
    )
    precio_nuevo_litro = models.DecimalField(max_digits=12, decimal_places=4)
    valor_ingresado = models.DecimalField(max_digits=12, decimal_places=4)
    unidad_ingresada = models.CharField(max_length=10, choices=UNIDAD_CHOICES)
    administrador = models.ForeignKey(
        Usuario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='historial_precios_combustible',
    )
    fecha_ajuste = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha_ajuste', '-id_historial_precio']

    def __str__(self):
        return f"{self.tipo}: {self.precio_nuevo_litro} USD/L"


class RendimientoVehiculoTipo(models.Model):
    tipo  = models.CharField(max_length=20, choices=[('AUTOMOVIL', 'AUTOMOVIL'), ('TAXI', 'TAXI'), ('MOTOCICLETA', 'MOTOCICLETA'), ('CAMION', 'CAMION'), ('CAMIONETA', 'CAMIONETA')])
    # kmpromedio
    km_l_promedio = models.FloatField(help_text="Rendimiento promedio en km/L")

    def __str__(self):
        return f"{self.tipo} - {self.km_l_promedio} km/L"



class UserSession(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    session_key = models.CharField(max_length=40, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.session_key}"