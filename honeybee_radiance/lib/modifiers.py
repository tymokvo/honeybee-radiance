"""Library of default modifiers for honeybee-radiance.

Default values are generic values to set the initial visible reflectance and
transmittance values in your model. There is no guarantee that these values exactly matches your model.
"""

from honeybee_radiance.primitive.material import Plastic, Glass


generic_exterior_wall = Plastic.from_single_reflectance('generic_ext_wall_0.35', 0.35)
generic_interior_wall = Plastic.from_single_reflectance('generic_int_wall_0.50', 0.5)
generic_ceiling = Plastic.from_single_reflectance('generic_ceiling_0.80', 0.8)
generic_roof = Plastic.from_single_reflectance('generic_roof_0.70', 0.7)
generic_floor = Plastic.from_single_reflectance('generic_floor_0.20', 0.2)
generic_exterior_glass = Glass.from_single_transmittance('generic_ext_glass_0.60', 0.6)
generic_interior_glass = Glass.from_single_transmittance('generic_int_glass_0.80', 0.8)
air_wall = Glass.from_single_transmissivity('air_wall', 1.0)
