import json
import helpers as h
import logic.action as action
import logic.converters as converters
import logic.validators as validators
from ckanext.metadata.common import plugins as p
from ckanext.metadata.common import app_globals

try:
    from collections import OrderedDict
except ImportError:
    from sqlalchemy.util import OrderedDict

class MetadataPlugin(p.SingletonPlugin, p.toolkit.DefaultDatasetForm):

    p.implements(p.IConfigurer)
    p.implements(p.IActions)
    p.implements(p.IRoutes, inherit=True)
    p.implements(p.IDatasetForm)
    p.implements(p.ITemplateHelpers)
    p.implements(p.IFacets, inherit=True)
    p.implements(p.IPackageController, inherit=True)

    # IConfigurer
    def update_config(self, config):
        templates = 'templates'
        public = 'public'

        p.toolkit.add_template_directory(config, templates)
        p.toolkit.add_public_directory(config, public)
        p.toolkit.add_resource('fanstatic', 'metadata')

        content_models = action.http_get_content_models()
        app_globals.mappings['usgin.content_models'] = 'usgin.content_models'
        data = {
            'usgin.content_models': config.get('usgin.content_models', content_models)
        }
        config.update(data)

    # IRoutes
    def before_map(self, map):
        view_controller = 'ckanext.metadata.controllers.view:ViewController'
        map.connect('metadata_iso_19139', '/metadata/iso-19139/{id}.xml',
                    controller=view_controller, action='show_iso_19139')

        ckan_version = h.md_get_vanilla_ckan_version()
        if ckan_version == '2.2.1':
            pkg_controller = 'ckanext.metadata.controllers.package_override:PackageContributeOverride'
            map.connect('pkg_skip_stage3', '/dataset/new_resource/{id}',
                        controller=pkg_controller, action='new_resource')
        return map

    # IActions
    def get_actions(self):
        return {
            'iso_19139': action.iso_19139,
            'get_content_models': action.get_content_models,
            'get_content_models_short': action.get_content_models_short,
        }

    # IDatasetForm
    def _modify_package_schema(self, schema):
        schema.update({
            'md_package': [p.toolkit.get_validator('ignore_missing'),
                             converters.convert_to_md_package_extras]
        })
        schema['resources'].update({
            'md_resource': [p.toolkit.get_validator('ignore_missing'),
                              converters.convert_to_md_resource_extras],
            'url': [validators.is_usgin_valid_data]
        })
        return schema

    def create_package_schema(self):
        schema = super(MetadataPlugin, self).create_package_schema()
        schema = self._modify_package_schema(schema)
        return schema

    def update_package_schema(self):
        schema = super(MetadataPlugin, self).update_package_schema()
        schema = self._modify_package_schema(schema)
        return schema

    def show_package_schema(self):
        schema = super(MetadataPlugin, self).show_package_schema()
        schema['tags']['__extras'].append(p.toolkit.get_converter('free_tags_only'))
        schema.update({
            'md_package': [p.toolkit.get_validator('ignore_missing'),
                             p.toolkit.get_converter('convert_from_extras')]
        })

        schema['resources'].update({
            'md_resource': [p.toolkit.get_validator('ignore_missing'),
                              p.toolkit.get_converter('convert_from_extras')],
        })

        return schema

    def is_fallback(self):
        # Return True to register this plugin as the default handler for
        # packages not handled by any other IDatasetForm plugin
        return True

    def package_types(self):
        return []

    # ITemplateHelpers
    def get_helpers(self):
        return {
            'md_get_vanilla_ckan_version': h.md_get_vanilla_ckan_version,
            'md_package_extras_processor': h.md_package_extras_processor,
            'md_resource_extras_processer': h.md_resource_extras_processer,
            'usgin_check_package_for_content_model': h.usgin_check_package_for_content_model,
        }

    # IPackageController
    def before_index(self, pkg_dict):
        if pkg_dict.get('md_package'):
            md_pkg = json.loads(pkg_dict.get('md_package'))

            # Authors
            md_agents = md_pkg.get('resourceDescription').get('citedSourceAgents')
            author_names = []
            organization_names = []
            for agent in md_agents:
                name = agent.get('relatedAgent').get('agentRole') \
                    .get('individual').get('personName', None)
                organization = agent.get('relatedAgent').get('agentRole') \
                    .get('organizationName', None)

                if name:
                    author_names.append(name)
                if organization:
                    organization_names.append(organization)

            pkg_dict['md_author_names'] = author_names
            pkg_dict['md_organization_names'] = organization_names

        if pkg_dict.get('tags'):
            content_models = []
            for tag in pkg_dict.get('tags'):
                tag = str(tag)
                if tag.startswith('usgincm:'):
                    content_models.append(tag.rsplit(":", 1)[1].title())
            pkg_dict['md_content_models'] = content_models

        return pkg_dict