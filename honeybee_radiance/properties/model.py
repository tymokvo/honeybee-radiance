# coding=utf-8
"""Model Radiance Properties."""
from ..sensorgrid import SensorGrid
from ..view import View
from ..dynamic.group import DynamicShadeGroup, DynamicSubFaceGroup
from ..modifierset import ModifierSet
from ..mutil import dict_to_modifier  # imports all modifiers classes
from ..modifier.material import BSDF
from ..lib.modifiers import black, generic_context

from honeybee.extensionutil import model_extension_dicts
from honeybee.checkdup import check_duplicate_identifiers
from honeybee.boundarycondition import Surface

try:
    from itertools import izip as zip  # python 2
except ImportError:
    pass   # python 3


class ModelRadianceProperties(object):
    """Radiance Properties for Honeybee Model.

    Args:
        host: A honeybee_core Model object that hosts these properties.

    Properties:
        * host
        * sensor_grids
        * views
        * modifiers
        * blk_modifiers
        * room_modifiers
        * face_modifiers
        * shade_modifiers
        * bsdf_modifiers
        * modifier_sets
        * dynamic_shade_groups
        * dynamic_subface_groups
        * shade_group_identifiers
        * subface_group_identifiers
        * has_sensor_grids
        * has_views
    """

    def __init__(self, host, sensor_grids=None, views=None):
        """Initialize Model radiance properties."""
        self._host = host
        self.sensor_grids = sensor_grids
        self.views = views

    @property
    def host(self):
        """Get the Model object hosting these properties."""
        return self._host

    @property
    def sensor_grids(self):
        """Get or set an array of SensorGrids that are associated with the model."""
        return tuple(self._sensor_grids)

    @sensor_grids.setter
    def sensor_grids(self, value):
        if value:
            try:
                self._sensor_grids = list(value)
                for obj in self._sensor_grids:
                    assert isinstance(obj, SensorGrid), 'Expected SensorGrid for Model' \
                        ' sensor_grids. Got {}.'.format(type(value))
            except (ValueError, TypeError):
                raise TypeError(
                    'Model sensor_grids must be an array. Got {}.'.format(type(value)))
        else:
            self._sensor_grids = []

    @property
    def views(self):
        """Get or set an array of Views that are associated with the model."""
        return tuple(self._views)

    @views.setter
    def views(self, value):
        if value:
            try:
                self._views = list(value)
                for obj in self._views:
                    assert isinstance(obj, View), 'Expected View for Model' \
                        ' views. Got {}.'.format(type(value))
            except (ValueError, TypeError):
                raise TypeError(
                    'Model views must be an array. Got {}.'.format(type(value)))
        else:
            self._views = []

    @property
    def modifiers(self):
        """A list of all unique modifiers in the model.

        This includes modifiers across all Faces, Apertures, Doors, Shades, Room
        ModifierSets, and modifiers for any dynamic states assigned to these objects.

        However, it excludes modifiers in the default modifier set. It also excludes
        blk_modifiers and the modifier_direct of any states, which can be obtained
        separately from the blk_modifiers property.
        """
        all_mods = self.room_modifiers + self.face_modifiers + self.shade_modifiers
        return list(set(all_mods))

    @property
    def blk_modifiers(self):
        """A list of all unique modifier_blk in the model.

        This includes modifier_blk across all Faces, Apertures, Doors, and Shades.
        It also includes modifier_direct for any dynamic states assigned to
        these objects.
        """
        modifiers = [black]
        for face in self.host.faces:  # check all orphaned Face modifiers
            self._check_and_add_face_modifier_blk(face, modifiers)
        for ap in self.host.orphaned_apertures:  # check all Aperture modifiers
            self._check_and_add_dynamic_obj_modifier_blk(ap, modifiers)
        for dr in self.host.orphaned_doors:  # check all Door modifiers
            self._check_and_add_dynamic_obj_modifier_blk(dr, modifiers)
        for shade in self.host.shades:
            self._check_and_add_dynamic_obj_modifier_blk(shade, modifiers)
        return list(set(modifiers))

    @property
    def room_modifiers(self):
        """A list of all unique modifiers assigned to Room ModifierSets."""
        room_mods = []
        for cnstr_set in self.modifier_sets:
            room_mods.extend(cnstr_set.modified_modifiers_unique)
        return list(set(room_mods))

    @property
    def face_modifiers(self):
        """A list of all unique modifiers assigned to Faces, Apertures and Doors.

        This includes both objects that are a part of Rooms as well as orphaned
        objects. It does not include the modifiers of any shades assigned to these
        objects. Nor does it include any blk modifiers.
        """
        modifiers = []
        for face in self.host.faces:  # check all orphaned Face modifiers
            self._check_and_add_face_modifier(face, modifiers)
        for ap in self.host.orphaned_apertures:  # check all Aperture modifiers
            self._check_and_add_obj_modifier(ap, modifiers)
        for dr in self.host.orphaned_doors:  # check all Door modifiers
            self._check_and_add_obj_modifier(dr, modifiers)
        return list(set(modifiers))

    @property
    def shade_modifiers(self):
        """A list of all unique modifiers assigned to Shades in the model."""
        modifiers = []
        for room in self.host.rooms:
            self._check_and_add_room_modifier_shade(room, modifiers)
        for face in self.host.orphaned_faces:
            self._check_and_add_face_modifier_shade(face, modifiers)
        for ap in self.host.orphaned_apertures:
            self._check_and_add_obj_modifier_shade(ap, modifiers)
        for dr in self.host.orphaned_doors:
            self._check_and_add_obj_modifier_shade(dr, modifiers)
        for shade in self.host.orphaned_shades:
            self._check_and_add_orphaned_shade_modifier(shade, modifiers)
        return list(set(modifiers))

    @property
    def bsdf_modifiers(self):
        """A list of all unique BSDF modifiers in the model.

        This includes any BSDF modifiers in both the Model.modifiers and the
        Model.blk_modifiers.
        """
        all_mods = self.modifiers + self.blk_modifiers
        return list(set(mod for mod in all_mods if isinstance(mod, BSDF)))

    @property
    def modifier_sets(self):
        """A list of all unique Room-Assigned ModifierSets in the Model."""
        modifier_sets = []
        for room in self.host.rooms:
            if room.properties.radiance._modifier_set is not None:
                if not self._instance_in_array(room.properties.radiance._modifier_set,
                                               modifier_sets):
                    modifier_sets.append(room.properties.radiance._modifier_set)
        return list(set(modifier_sets))  # catch equivalent modifier sets

    @property
    def dynamic_shade_groups(self):
        """Get a list of DynamicShadeGroups in the model.

        These can be used to write dynamic shades into radiance files.
        """
        # gather all of the shades with a common identifier into groups
        group_dict = {}
        for shade in self.host.shades:
            if shade.properties.radiance._dynamic_group_identifier:
                group_id = shade.properties.radiance._dynamic_group_identifier
                try:
                    group_dict[group_id].append(shade)
                except KeyError:
                    group_dict[group_id] = [shade]
        # return DynamicShadeGroup objects
        return [DynamicShadeGroup(ident, shades)for ident, shades in group_dict.items()]

    @property
    def dynamic_subface_groups(self):
        """Get a list of DynamicSubFaceGroups in the model.

        These can be used to write dynamic Apertures and Doors into radiance files.
        """
        # gather all of the subfaces with a common identifier into groups
        group_dict = {}
        for subface in self.host.apertures + self.host.doors:
            if subface.properties.radiance._dynamic_group_identifier:
                group_id = subface.properties.radiance._dynamic_group_identifier
                try:
                    group_dict[group_id].append(subface)
                except KeyError:
                    group_dict[group_id] = [subface]
        # return DynamicSubFaceGroup objects
        return [DynamicSubFaceGroup(ident, subf)for ident, subf in group_dict.items()]

    @property
    def shade_group_identifiers(self):
        """Get a list of identifers for all the DynamicShadeGroups in the model."""
        group_ids = set()
        for shade in self.host.shades:
            if shade.properties.radiance._dynamic_group_identifier:
                group_ids.add(shade.properties.radiance._dynamic_group_identifier)
        return list(group_ids)

    @property
    def subface_group_identifiers(self):
        """Get a list of identifers for all the DynamicSubFaceGroups in the model."""
        group_ids = set()
        for subface in self.host.apertures + self.host.doors:
            if subface.properties.radiance._dynamic_group_identifier:
                group_ids.add(subface.properties.radiance._dynamic_group_identifier)
        return list(group_ids)

    @property
    def has_sensor_grids(self):
        """Get a boolean for whether there are sensor grids assigned to the model."""
        return len(self._sensor_grids) != 0

    @property
    def has_views(self):
        """Get a boolean for whether there are views assigned to the model."""
        return len(self._views) != 0

    def remove_sensor_grids(self):
        """Remove all sensor grids from the model."""
        self._sensor_grids = []

    def remove_views(self):
        """Remove all views from the model."""
        self._views = []

    def add_sensor_grid(self, sensor_grid):
        """Add a SensorGrid to this model.

        Args:
            sensor_grid: A SensorGrid to add to this model.
        """
        assert isinstance(sensor_grid, SensorGrid), \
            'Expected SensorGrid. Got {}.'.format(type(sensor_grid))
        self._sensor_grids.append(sensor_grid)

    def add_view(self, view):
        """Add a View to this model.

        Args:
            view: A View to add to this model.
        """
        assert isinstance(view, View), 'Expected View. Got {}.'.format(type(view))
        self._views.append(view)

    def add_sensor_grids(self, sensor_grids):
        """Add a list of SensorGrids to this model."""
        for grid in sensor_grids:
            self.add_sensor_grid(grid)

    def add_views(self, views):
        """Add a list of Views to this model."""
        for view in views:
            self.add_view(view)

    def faces_by_blk(self):
        """Get all Faces in the model separated by their blk property.

        This method will also ensure that any faces with Surface boundary condition
        only have one of such objects in the output lists.

        Returns:
            A tuple with 2 lists:

            -   faces: A list of all  faces without a unique modifier_blk.

            -   faces_blk: A list of all opaque faces that have a unique modifier_blk.
        """
        faces = []
        faces_blk = []
        interior_faces = set()
        for face in self.host.faces:
            if isinstance(face.boundary_condition, Surface):
                if face.identifier in interior_faces:
                    continue
                interior_faces.add(face.boundary_condition.boundary_condition_object)
            if face.properties.radiance._modifier_blk:
                faces_blk.append(face)
            else:
                faces.append(face)
        return faces, faces_blk

    def subfaces_by_blk(self):
        """Get model sub-faces (Apertures, Doors) separated by their blk property.

        Dynamic sub-faces will be excluded from the output lists.
        This method will also ensure that any interior sub-faces (with Surface
        boundary condition) only have one of such objects in the output lists.

        Returns:
            A tuple with 2 lists:

            -   subfaces: A list of all sub-faces without a unique modifier_blk
                (just using the default black).

            -   subfaces_blk: A list of all sub-faces that have a unique modifier_blk.
        """
        subfaces = []
        subfaces_blk = []
        interior_ids = set()
        for subf in self.host.apertures + self.host.doors:
            if subf.properties.radiance.dynamic_group_identifier:
                continue  # sub-face will be accounted for in the dynamic objects
            if isinstance(subf.boundary_condition, Surface):
                if subf.identifier in interior_ids:
                    continue
                interior_ids.add(subf.boundary_condition.boundary_condition_object)
            if subf.properties.radiance._modifier_blk:
                subfaces_blk.append(subf)
            else:
                subfaces.append(subf)
        return subfaces, subfaces_blk

    def shades_by_blk(self):
        """Get all Shades in the model separated by their blk property.

        Dynamic shades will be excluded from the output lists.

        Returns:
            A tuple with 2 lists:

            -   shades: A list of all opaque shades without a unique modifier_blk
                (just using the default black or transparent modifier).

            -   shades_blk: A list of all opaque shades that have a unique modifier_blk.
        """
        shades = []
        shades_blk = []
        for shade in self.host.shades:
            if shade.properties.radiance.dynamic_group_identifier:
                continue  # shade will be accounted for in the dynamic objects
            if shade.properties.radiance._modifier_blk:
                shades_blk.append(shade)
            else:
                shades.append(shade)
        return shades, shades_blk

    def move(self, moving_vec):
        """Move all sensor_grid and view geometry along a vector.

        Args:
            moving_vec: A ladybug_geometry Vector3D with the direction and distance
                to move the objects.
        """
        for grid in self._sensor_grids:
            grid.move(moving_vec)
        for view in self._views:
            view.move(moving_vec)

    def rotate(self, axis, angle, origin):
        """Rotate all sensor_grid and view geometry.

        Args:
            axis: A ladybug_geometry Vector3D axis representing the axis of rotation.
            angle: An angle for rotation in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        for grid in self._sensor_grids:
            grid.rotate(axis, angle, origin)
        for view in self._views:
            view.rotate(axis, angle, origin)

    def rotate_xy(self, angle, origin):
        """Rotate all sensor_grids and views counterclockwise in the world XY plane.

        Args:
            angle: An angle in degrees.
            origin: A ladybug_geometry Point3D for the origin around which the
                object will be rotated.
        """
        for grid in self._sensor_grids:
            grid.rotate_xy(angle, origin)
        for view in self._views:
            view.rotate_xy(angle, origin)

    def reflect(self, plane):
        """Reflect all sensor_grid and view geometry across a plane.

        Args:
            plane: A ladybug_geometry Plane across which the object will
                be reflected.
        """
        for grid in self._sensor_grids:
            grid.reflect(plane)
        for view in self._views:
            view.reflect(plane)

    def scale(self, factor, origin=None):
        """Scale all sensor_grid and view geometry by a factor.

        Args:
            factor: A number representing how much the object should be scaled.
            origin: A ladybug_geometry Point3D representing the origin from which
                to scale. If None, it will be scaled from the World origin (0, 0, 0).
        """
        for grid in self._sensor_grids:
            grid.scale(factor, origin)
        for view in self._views:
            view.scale(factor, origin)

    def check_all(self, raise_exception=True):
        """Check all of the aspects of the Model radiance properties.

        Args:
            raise_exception: Boolean to note whether a ValueError should be raised
                if any errors are found. If False, this method will simply
                return a text string with all errors that were found.

        Returns:
            A text string with all errors that were found. This string will be empty
            of no errors were found.
        """
        msgs = []
        # perform checks for key honeybee model schema rules
        msgs.append(self.check_duplicate_modifier_identifiers(False))
        msgs.append(self.check_duplicate_modifier_set_identifiers(False))
        msgs.append(self.check_duplicate_sensor_grid_identifiers(False))
        msgs.append(self.check_duplicate_view_identifiers(False))
        msgs.append(self.check_sensor_grid_rooms_in_model(False))
        msgs.append(self.check_view_rooms_in_model(False))
        # output a final report of errors or raise an exception
        full_msgs = [msg for msg in msgs if msg != '']
        full_msg = '\n'.join(full_msgs)
        if raise_exception and len(full_msgs) != 0:
            raise ValueError(full_msg)
        return full_msg

    def check_duplicate_modifier_identifiers(self, raise_exception=True):
        """Check that there are no duplicate Modifier identifiers in the model."""
        return check_duplicate_identifiers(
            self.modifiers, raise_exception, 'Radiance Modifier')

    def check_duplicate_modifier_set_identifiers(self, raise_exception=True):
        """Check that there are no duplicate ModifierSet identifiers in the model."""
        return check_duplicate_identifiers(
            self.modifier_sets, raise_exception, 'ModifierSet')

    def check_duplicate_sensor_grid_identifiers(self, raise_exception=True):
        """Check that there are no duplicate SensorGrid identifiers in the model."""
        return check_duplicate_identifiers(
            self.sensor_grids, raise_exception, 'SensorGrid')

    def check_duplicate_view_identifiers(self, raise_exception=True):
        """Check that there are no duplicate View identifiers in the model."""
        return check_duplicate_identifiers(self.views, raise_exception, 'View')

    def check_sensor_grid_rooms_in_model(self, raise_exception=True):
        """Check that the room_identifiers of SenorGrids are in the model."""
        grid_ids = [grid.room_identifier for grid in self.sensor_grids]
        room_ids = set(room.identifier for room in self.host.rooms)
        missing_rooms = set()
        for grid in grid_ids:
            if grid not in room_ids:
                missing_rooms.add(grid)
        if len(missing_rooms) != 0:
            msg = 'The model has the following missing rooms referenced by sensor ' \
                'grids:\n{}'.format('\n'.join(missing_rooms))
            if raise_exception:
                raise ValueError(msg)
            return msg
        return ''

    def check_view_rooms_in_model(self, raise_exception=True):
        """Check that the room_identifiers of Views are in the model."""
        view_ids = [view.room_identifier for view in self.views]
        room_ids = set(room.identifier for room in self.host.rooms)
        missing_rooms = set()
        for view in view_ids:
            if view not in room_ids:
                missing_rooms.add(view)
        if len(missing_rooms) != 0:
            msg = 'The model has the following missing rooms referenced by ' \
                'views:\n{}'.format('\n'.join(missing_rooms))
            if raise_exception:
                raise ValueError(msg)
            return msg
        return ''

    def apply_properties_from_dict(self, data):
        """Apply the radiance properties of a dictionary to the host Model of this object.

        Args:
            data: A dictionary representation of an entire honeybee-core Model.
                Note that this dictionary must have ModelRadianceProperties in order
                for this method to successfully apply the radiance properties.
        """
        assert 'radiance' in data['properties'], \
            'Dictionary possesses no ModelRadianceProperties.'

        modifiers, modifier_sets = self.load_properties_from_dict(data)

        # collect lists of radiance property dictionaries
        room_e_dicts, face_e_dicts, shd_e_dicts, ap_e_dicts, dr_e_dicts = \
            model_extension_dicts(data, 'radiance', [], [], [], [], [])

        # apply radiance properties to objects using the radiance property dictionaries
        for room, r_dict in zip(self.host.rooms, room_e_dicts):
            if r_dict is not None:
                room.properties.radiance.apply_properties_from_dict(
                    r_dict, modifier_sets)
        for face, f_dict in zip(self.host.faces, face_e_dicts):
            if f_dict is not None:
                face.properties.radiance.apply_properties_from_dict(
                    f_dict, modifiers)
        for aperture, a_dict in zip(self.host.apertures, ap_e_dicts):
            if a_dict is not None:
                aperture.properties.radiance.apply_properties_from_dict(
                    a_dict, modifiers)
        for door, d_dict in zip(self.host.doors, dr_e_dicts):
            if d_dict is not None:
                door.properties.radiance.apply_properties_from_dict(
                    d_dict, modifiers)
        for shade, s_dict in zip(self.host.shades, shd_e_dicts):
            if s_dict is not None:
                shade.properties.radiance.apply_properties_from_dict(
                    s_dict, modifiers)

        # apply the sensor grids and views if they are in the data.
        rad_data = data['properties']['radiance']
        if 'sensor_grids' in rad_data and rad_data['sensor_grids'] is not None:
            self.sensor_grids = \
                [SensorGrid.from_dict(grid) for grid in rad_data['sensor_grids']]
        if 'views' in rad_data and rad_data['views'] is not None:
            self.views = [View.from_dict(view) for view in rad_data['views']]

    def to_dict(self):
        """Return Model radiance properties as a dictionary."""
        base = {'radiance': {'type': 'ModelRadianceProperties'}}

        # add all ModifierSets to the dictionary
        base['radiance']['modifier_sets'] = []
        modifier_sets = self.modifier_sets
        for mod_set in modifier_sets:
            base['radiance']['modifier_sets'].append(mod_set.to_dict(abridged=True))

        # add all unique Modifiers to the dictionary
        room_mods = []
        for mod_set in modifier_sets:
            room_mods.extend(mod_set.modified_modifiers_unique)
        all_mods = room_mods + self.face_modifiers + self.shade_modifiers
        modifiers = list(set(all_mods))
        base['radiance']['modifiers'] = []
        for mod in modifiers:
            base['radiance']['modifiers'].append(mod.to_dict())

        # add the sensor grids and views to the dictionary
        if len(self._sensor_grids) != 0:
            base['radiance']['sensor_grids'] = \
                [grid.to_dict() for grid in self._sensor_grids]
        if len(self._views) != 0:
            base['radiance']['views'] = [view.to_dict() for view in self._views]

        return base

    def duplicate(self, new_host=None):
        """Get a copy of this object.

        new_host: A new Model object that hosts these properties.
            If None, the properties will be duplicated with the same host.
        """
        _host = new_host or self._host
        return ModelRadianceProperties(_host, self._sensor_grids, self._views)

    @staticmethod
    def load_properties_from_dict(data):
        """Load model radiance properties of a dictionary to Python objects.

        Loaded objects include Modifiers and ModifierSets.

        The function is called when re-serializing a Model object from a dictionary
        to load honeybee_radiance objects into their Python object form before
        applying them to the Model geometry.

        Args:
            data: A dictionary representation of an entire honeybee-core Model.
                Note that this dictionary must have ModelRadianceProperties in order
                for this method to successfully load the radiance properties.

        Returns:
            A tuple with two elements

            -   modifiers: A dictionary with identifiers of modifiers as keys and Python
                modifier objects as values.

            -   modifier_sets: A dictionary with identifiers of modifier sets as keys
                and Python modifier set objects as values.
        """
        assert 'radiance' in data['properties'], \
            'Dictionary possesses no ModelRadianceProperties.'

        # process all modifiers in the ModelRadianceProperties dictionary
        modifiers = {}
        for mod in data['properties']['radiance']['modifiers']:
            modifiers[mod['identifier']] = dict_to_modifier(mod)

        # process all modifier sets in the ModelRadianceProperties dictionary
        modifier_sets = {}
        if 'modifier_sets' in data['properties']['radiance'] and \
                data['properties']['radiance']['modifier_sets'] is not None:
            for m_set in data['properties']['radiance']['modifier_sets']:
                if m_set['type'] == 'ModifierSet':
                    modifier_sets[m_set['identifier']] = ModifierSet.from_dict(m_set)
                else:
                    modifier_sets[m_set['identifier']] = \
                        ModifierSet.from_dict_abridged(m_set, modifiers)

        return modifiers, modifier_sets

    def _check_and_add_room_modifier_shade(self, room, modifiers):
        """Check if a modifier is assigned to a Room's shades and add it to a list."""
        self._check_and_add_obj_modifier_shade(room, modifiers)
        for face in room.faces:  # check all Face modifiers
            self._check_and_add_face_modifier_shade(face, modifiers)

    def _check_and_add_face_modifier_shade(self, face, modifiers):
        """Check if a modifier is assigned to a Face's shades and add it to a list."""
        self._check_and_add_obj_modifier_shade(face, modifiers)
        for ap in face.apertures:  # check all Aperture modifiers
            self._check_and_add_obj_modifier_shade(ap, modifiers)
        for dr in face.doors:  # check all Door Shade modifiers
            self._check_and_add_obj_modifier_shade(dr, modifiers)

    def _check_and_add_obj_modifier_shade(self, subf, modifiers):
        """Check if a modifier is assigned to an object's shades and add it to a list."""
        for shade in subf.shades:
            self._check_and_add_dynamic_obj_modifier(shade, modifiers)

    def _check_and_add_face_modifier(self, face, modifiers):
        """Check if a modifier is assigned to a face and add it to a list."""
        self._check_and_add_obj_modifier(face, modifiers)
        for ap in face.apertures:  # check all Aperture modifiers
            self._check_and_add_dynamic_obj_modifier(ap, modifiers)
        for dr in face.doors:  # check all Door modifiers
            self._check_and_add_dynamic_obj_modifier(dr, modifiers)

    def _check_and_add_face_modifier_blk(self, face, modifiers):
        """Check if a modifier_blk is assigned to a face and add it to a list."""
        self._check_and_add_obj_modifier_blk(face, modifiers)
        for ap in face.apertures:  # check all Aperture modifiers
            self._check_and_add_dynamic_obj_modifier_blk(ap, modifiers)
        for dr in face.doors:  # check all Door modifiers
            self._check_and_add_dynamic_obj_modifier_blk(dr, modifiers)

    def _check_and_add_obj_modifier(self, obj, modifiers):
        """Check if a modifier is assigned to an object and add it to a list."""
        mod = obj.properties.radiance._modifier
        if mod is not None:
            if not self._instance_in_array(mod, modifiers):
                modifiers.append(mod)

    def _check_and_add_dynamic_obj_modifier(self, obj, modifiers):
        """Check if a modifier is assigned to a dynamic object and add it to a list."""
        mod = obj.properties.radiance._modifier
        if mod is not None:
            if not self._instance_in_array(mod, modifiers):
                modifiers.append(mod)
        for st in obj.properties.radiance._states:
            stm = (st._modifier, st._modifier_direct) + \
                tuple(s.modifier for s in st._shades)
            for mod in stm:
                if mod is not None:
                    if not self._instance_in_array(mod, modifiers):
                        modifiers.append(mod)

    def _check_and_add_obj_modifier_blk(self, obj, modifiers):
        """Check if a modifier_blk is assigned to an object and add it to a list."""
        mod = obj.properties.radiance._modifier_blk
        if mod is not None:
            if not self._instance_in_array(mod, modifiers):
                modifiers.append(mod)

    def _check_and_add_dynamic_obj_modifier_blk(self, obj, modifiers):
        """Check if a modifier_blk is assigned to a dynamic object and add it to a list.
        """
        mod = obj.properties.radiance._modifier_blk
        if mod is not None:
            if not self._instance_in_array(mod, modifiers):
                modifiers.append(mod)
        for st in obj.properties.radiance._states:
            for s in st._shades:
                mod = s.modifier
                if mod is not None:
                    if not self._instance_in_array(mod, modifiers):
                        modifiers.append(mod)

    def _check_and_add_orphaned_shade_modifier(self, obj, modifiers):
        """Check if a modifier is assigned to an object and add it to a list."""
        mod = obj.properties.radiance._modifier
        if mod is not None:
            if not self._instance_in_array(mod, modifiers):
                modifiers.append(mod)
        else:
            if not self._instance_in_array(generic_context, modifiers):
                modifiers.append(generic_context)
        for st in obj.properties.radiance._states:
            stm = (st._modifier, st._modifier_direct) + \
                tuple(s.modifier for s in st._shades)
            for mod in stm:
                if mod is not None:
                    if not self._instance_in_array(mod, modifiers):
                        modifiers.append(mod)

    @staticmethod
    def _instance_in_array(object_instance, object_array):
        """Check if a specific object instance is already in an array.

        This can be much faster than  `if object_instance in object_array`
        when you expect to be testing a lot of the same instance of an object for
        inclusion in an array since the builtin method uses an == operator to
        test inclusion.
        """
        for val in object_array:
            if val is object_instance:
                return True
        return False

    def ToString(self):
        return self.__repr__()

    def __repr__(self):
        return 'Model Radiance Properties: [host: {}]'.format(self.host.display_name)
