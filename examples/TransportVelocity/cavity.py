"""Lid driven cavity using the Transport Velocity formulation"""

# PyZoltan imports
from pyzoltan.core.carray import LongArray

# PySPH imports
from pysph.base.utils import get_particle_array
from pysph.base.kernels import Gaussian, WendlandQuintic, CubicSpline
from pysph.solver.solver import Solver
from pysph.solver.application import Application
from pysph.sph.integrator import TransportVelocityIntegrator

# the eqations
from pysph.sph.equations import Group
from pysph.sph.transport_velocity_equations import TransportVelocitySummationDensity,\
    TransportVelocitySolidWall, TransportVelocityMomentumEquation

# numpy
import numpy as np

# domain and reference values
L = 1.0; Umax = 1.0
c0 = 10 * Umax; rho0 = 1.0
p0 = c0*c0/rho0

# Reynolds number and kinematic viscosity
Re = 1000; nu = Umax * L/Re

# Numerical setup
nx = 80; dx = L/nx
ghost_extent = 5 * dx
hdx = 1.2

def create_particles(empty=False, **kwargs):
    if empty:
        fluid = get_particle_array(name='fluid')
        solid = get_particle_array(name='solid')
    else:
        # create all the particles
        _x = np.arange( -ghost_extent - dx/2, L + ghost_extent + dx/2, dx )
        x, y = np.meshgrid(_x, _x); x = x.ravel(); y = y.ravel()

        # sort out the fluid and the solid
        indices = []
        for i in range(x.size):
            if ( (x[i] > 0.0) and (x[i] < L) ):
                if ( (y[i] > 0.0) and (y[i] < L) ):
                    indices.append(i)

        to_extract = LongArray(len(indices)); to_extract.set_data(np.array(indices))

        # create the arrays
        solid = get_particle_array(name='solid', x=x, y=y)

        # remove the fluid particles from the solid
        fluid = solid.extract_particles(to_extract); fluid.set_name('fluid')
        solid.remove_particles(to_extract)
        
        print "Lid driven cavity :: Re = %d, nfluid = %d, nsolid=%d"%(
            Re, fluid.get_number_of_particles(),
            solid.get_number_of_particles())

    # add requisite properties to the arrays:
    # particle volume
    fluid.add_property( {'name': 'V'} )
    solid.add_property( {'name': 'V'} )
        
    # advection velocities and accelerations
    fluid.add_property( {'name': 'uhat'} )
    fluid.add_property( {'name': 'vhat'} )

    solid.add_property( {'name': 'uhat'} )
    solid.add_property( {'name': 'vhat'} )

    fluid.add_property( {'name': 'auhat'} )
    fluid.add_property( {'name': 'avhat'} )

    fluid.add_property( {'name': 'au'} )
    fluid.add_property( {'name': 'av'} )
    fluid.add_property( {'name': 'aw'} )
    
    # kernel summation correction for the solid
    solid.add_property( {'name': 'wij'} )

    # imopsed velocity on the solid
    solid.add_property( {'name': 'u0'} )
    solid.add_property( {'name': 'v0'} )                         
        
    # setup the particle properties
    if not empty:
        volume = dx * dx

        # mass is set to get the reference density of rho0
        fluid.m[:] = volume * rho0
        solid.m[:] = volume * rho0

        # volume is set as dx^2
        fluid.V[:] = 1./volume
        solid.V[:] = 1./volume

        # smoothing lengths
        fluid.h[:] = hdx * dx
        solid.h[:] = hdx * dx
        
        # imposed horizontal velocity on the lid
        solid.u0[:] = 0.0
        solid.v0[:] = 0.0
        for i in range(solid.get_number_of_particles()):
            if solid.y[i] > L:
                solid.u0[i] = Umax
                
    # return the particle list
    return [fluid, solid]

# Create the application.
app = Application()

# Create the kernel
kernel = WendlandQuintic(dim=2)

# Create a solver.
solver = Solver(
    kernel=kernel, dim=2, integrator_type=TransportVelocityIntegrator)

# Setup default parameters.
solver.set_time_step(1e-5)
solver.set_final_time(5)

equations = [

    # Summation density for the fluid phase
    Group(
        equations=[
            TransportVelocitySummationDensity(
                dest='fluid', sources=['fluid','solid'], rho0=rho0, c0=c0),
            ]),
    
    # boundary conditions for the solid wall
    Group(
        equations=[
            TransportVelocitySolidWall(
                dest='solid', sources=['fluid',], rho0=rho0, p0=p0),
            ]),
    
    # acceleration equation
    Group(
        equations=[
            TransportVelocityMomentumEquation(
                dest='fluid', sources=['fluid', 'solid'], nu=nu, pb=p0)
            ]),
    ]

# Setup the application and solver.  This also generates the particles.
app.setup(solver=solver, equations=equations, 
          particle_factory=create_particles)

with open('cavity.pyx', 'w') as f:
    app.dump_code(f)

app.run()