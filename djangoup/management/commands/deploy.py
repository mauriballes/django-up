"""
Module for Deploy Commands.
"""
from argparse import ArgumentParser
import os
import re
import shutil

from fabric2 import Connection
from invoke import run as runcommand
import yaml

from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    """Command Class for Deploy Commands."""
    help = 'Deploy your Django Project'

    def add_arguments(self, parser: ArgumentParser):
        parser.add_argument(
            '--init', '-i',
            action='store_true',
            dest='init',
            help='Init Configuration for Deploying Project.')

        parser.add_argument(
            '--build', '-b',
            action='store_true',
            dest='build',
            help='Build files and dirs that are necessary for deploying project.')

    def handle(self, *args, **options):
        project_root_path = settings.BASE_DIR
        current_dir_path = os.path.dirname(os.path.abspath(__file__))

        if options['init']:
            self.handle_init_command(project_root_path, current_dir_path)
        elif options['build']:
            self.handle_build_project_for_deploy(project_root_path, current_dir_path)
        else:
            self.handle_deploy_project(project_root_path)

    def handle_init_command(self, project_root_path, current_dir_path):
        """Create deploy.yml file for doing initial config for deploying the project."""
        deploy_file_path_for_copy = '{}/deploy.example.yml'.format(current_dir_path)
        deploy_file_path_on_project_root_path = '{}/deploy.yml'.format(project_root_path)

        if not os.path.isfile(deploy_file_path_on_project_root_path):
            shutil.copyfile(deploy_file_path_for_copy, deploy_file_path_on_project_root_path)
            self.stdout.write('- Copy deploy.yml to root path')
        else:
            self.stdout.write('- deploy.yml is already in root path')

        self.stdout.write(self.style.SUCCESS('Successfully Init Deploy'))

    def handle_build_project_for_deploy(self, project_root_path, current_dir_path):
        """Generate settings folder and gunicorn config file from deploy.yml."""
        error_on_build_project_message = 'Error on build for deploying project'

        deploy_file_path = '{}/deploy.yml'.format(project_root_path)
        if not os.path.isfile(deploy_file_path):
            self.stdout.write('- deploy.yml is not created. You can use python manage.py deploy --init')
            self.stderr.write(error_on_build_project_message)
            return

        deploy_settings = self.get_deploy_yaml_config(project_root_path)
        if not deploy_settings:
            self.stdout.write('- deploy.yml is bad configured. Check the file please')
            self.stderr.write(error_on_build_project_message)
            return

        gunicorn_file_path = '{}/gunicorn.conf.py'.format(project_root_path)
        if not os.path.isfile(gunicorn_file_path):
            self.generate_gunicorn_config_file(deploy_settings, project_root_path, current_dir_path)
            self.stdout.write('- Gunicorn file created successfully')
        else:
            self.stdout.write('- Gunicorn file is already created')

        project_name = deploy_settings.get('project_name')
        project_config_folder_path = '{}/{}'.format(project_root_path, project_name)
        settings_folder_path = '{}/settings'.format(project_config_folder_path)
        if not self.check_settings_folder_is_already_exist(settings_folder_path):
            self.generate_settings_folder(settings_folder_path)
            creating_result_success = self.generate_new_settings_file(project_config_folder_path, current_dir_path)

            if not creating_result_success:
                self.stdout.write('- Project name could be wrong on deploy.yml')
                self.stderr.write(error_on_build_project_message)
                return

            self.generate_environment_files(settings_folder_path)
            self.add_local_settings_to_gitignore(project_root_path, project_name)
            self.remove_old_settings_file(project_config_folder_path)
            self.stdout.write('- Settings folder created successfully')
        else:
            self.stdout.write('- Settings folder is already created')

        self.stdout.write(self.style.SUCCESS('Successfully Build files'))

    def handle_deploy_project(self, project_root_path):
        """Handle deploy process when execute python manage.py deploy command."""
        error_on_deploy_project_message = 'Error on deploy project'
        self.stdout.write(self.style.WARNING('- Check stuffs for deploy'))

        (checking_result_success, checking_message) = self.check_requirements_for_deploy(project_root_path)
        self.stdout.write(self.style.WARNING(checking_message))
        if not checking_result_success:
            self.stderr.write(error_on_deploy_project_message)
            return

        deploy_settings = self.get_deploy_yaml_config(project_root_path)
        same_git_hashes = self.run_git_tasks(deploy_settings)
        if not same_git_hashes:
            self.stdout.write(self.style.WARNING('- Branchs are not updated. Run git push to sync changes'))
            self.stderr.write(error_on_deploy_project_message)
            return
        else:
            self.stdout.write(self.style.WARNING('- Git branches updated'))

        server_host = deploy_settings.get('server_ip')
        server_user = deploy_settings.get('server_user')
        server_port = deploy_settings.get('server_ssh_port')
        server_connection = Connection(host=server_host, user=server_user, port=server_port)
        success_server_build = self.build_server_structure(server_connection, deploy_settings)
        if not success_server_build:
            server_connection.close()
            self.stdout.write(self.style.WARNING('- Error on build server structure'))
            self.stderr.write(error_on_deploy_project_message)
            return

        self.stdout.write(self.style.SUCCESS('Successfully Deploy'))

    def check_requirements_for_deploy(self, project_root_path):
        """Check all the requirements for execute a deploy."""
        deploy_file_path = '{}/deploy.yml'.format(project_root_path)
        if not os.path.isfile(deploy_file_path):
            return False, '- deploy.yml is not created. You can use python manage.py deploy --init'

        deploy_settings = self.get_deploy_yaml_config(project_root_path)
        if not deploy_settings:
            return False, '- deploy.yml is bad configured. Check the file please'

        gunicorn_file_path = '{}/gunicorn.conf.py'.format(project_root_path)
        if not os.path.isfile(gunicorn_file_path):
            return False, '- gunicorn.conf.py is not created. You can use python manage.py deploy --build'

        project_name = deploy_settings.get('project_name')
        settings_folder_path = '{}/{}/settings'.format(project_root_path, project_name)
        if not os.path.exists(settings_folder_path):
            return False, '- settings folder is not created. You can use python manage.py deploy --build'

        return True, '- All your settings files are ready'

    @classmethod
    def run_git_tasks(cls, deploy_settings):
        """Run git tasks to check project status"""
        branch = deploy_settings.get('branch')
        remote_name = deploy_settings.get('remote_name')

        git_local_hash = runcommand('git rev-parse HEAD')
        git_remote_hash = runcommand('git rev-parse {}/{}'.format(remote_name, branch))
        return git_local_hash.stdout == git_remote_hash.stdout

    def build_server_structure(self, server_connection, deploy_settings):
        """Build a server structure for deploy."""
        success_build_folder = self.build_server_folders(server_connection, deploy_settings)
        if not success_build_folder:
            self.stdout.write(self.style.WARNING('- Error building folders on server'))
            return False
        else:
            self.stdout.write(self.style.WARNING('- Project folders build successfully'))

        success_build_project = self.build_project_on_server(server_connection, deploy_settings)
        if not success_build_project:
            self.stdout.write(self.style.WARNING('- Error building project on server'))
            return False
        else:
            self.stdout.write(self.style.WARNING('- Project application build successfully'))

        success_build_venv = self.build_venv_on_server(server_connection, deploy_settings)
        if not success_build_venv:
            self.stdout.write(self.style.WARNING('- Error building venv on server'))
            return False
        else:
            self.stdout.write(self.style.WARNING('- Project venv build successfully'))

        success_migration_run = self.run_migrations(server_connection, deploy_settings)
        if not success_migration_run:
            self.stdout.write(self.style.WARNING('- Error running migrations on server'))
            return False
        else:
            self.stdout.write(self.style.WARNING('- Run migrations on database successfully'))

        success_assets_collect = self.generate_assets_collect(server_connection, deploy_settings)
        if not success_assets_collect:
            self.stdout.write(self.style.WARNING('- Error collecting assets on server'))
            return False
        else:
            self.stdout.write(self.style.WARNING('- Collect assets action successfully'))

        success_gunicorn_service = self.run_gunicorn_service(server_connection, deploy_settings)
        if not success_gunicorn_service:
            self.stdout.write(self.style.WARNING('- Error starting gunicorn service'))
            return False
        else:
            self.stdout.write(self.style.WARNING('- Gunicorn service start'))

        return True

    @classmethod
    def build_server_folders(cls, server_connection, deploy_settings):
        """Build folders on server."""
        project_folder_path = deploy_settings.get('server_project_path')
        venv_folder_path = deploy_settings.get('server_venv_path')
        mkdir_command = 'mkdir -p {}'

        create_project_folder = server_connection.run(mkdir_command.format(project_folder_path))
        create_venv_folder = server_connection.run(mkdir_command.format(venv_folder_path))

        successful_exit_code = 0
        return create_project_folder.exited == successful_exit_code and create_venv_folder.exited == successful_exit_code

    @classmethod
    def build_project_on_server(cls, server_connection, deploy_settings):
        """Clone or pull new changes to the project."""
        project_folder_path = deploy_settings.get('server_project_path')
        git_remote_server_url = deploy_settings.get('repo_url')
        list_command_for_count = 'ls -1 {} | wc -l'

        has_files_on_project = server_connection.run(list_command_for_count.format(project_folder_path), hide=True)
        files_count_on_project = int(has_files_on_project.stdout)

        branch = deploy_settings.get('branch')
        remote_name = deploy_settings.get('remote_name')

        git_clone_command = 'git clone {} {}'.format(git_remote_server_url, project_folder_path)
        git_pull_command = 'cd {} && git pull {} {}'.format(project_folder_path, remote_name, branch)
        if files_count_on_project:
            git_result_command = server_connection.run(git_pull_command)
        else:
            git_result_command = server_connection.run(git_clone_command)

        successful_exit_code = 0
        return git_result_command.exited == successful_exit_code

    @classmethod
    def build_venv_on_server(cls, server_connection, deploy_settings):
        """Build venv with dependencies."""
        venv_folder_path = deploy_settings.get('server_venv_path')
        project_folder_path = deploy_settings.get('server_project_path')
        python_runtime_path = deploy_settings.get('python_runtime_venv')
        list_command_for_count = 'ls -1 {} | wc -l'
        successful_exit_code = 0

        has_files_on_venv = server_connection.run(list_command_for_count.format(venv_folder_path), hide=True)
        files_count_on_venv = int(has_files_on_venv.stdout)

        virtualenv_create_command = '{0} -m virtualenv -p {0} {1}'.format(python_runtime_path, venv_folder_path)
        if not files_count_on_venv:
            virtualenv_created_result = server_connection.run(virtualenv_create_command)
            if virtualenv_created_result.exited != successful_exit_code:
                return False

        install_dependecies_command = '{}/bin/pip install -r {}/requirements.txt'.format(venv_folder_path, project_folder_path)
        install_dependencies_result = server_connection.run(install_dependecies_command)
        if install_dependencies_result.exited != successful_exit_code:
            return False

        return True

    @classmethod
    def run_migrations(cls, server_connection, deploy_settings):
        """Running migrations on server database."""
        venv_folder_path = deploy_settings.get('server_venv_path')
        project_folder_path = deploy_settings.get('server_project_path')
        project_name = deploy_settings.get('project_name')
        successful_exit_code = 0

        run_migration_command = '{}/bin/python {}/manage.py migrate --settings={}.settings'.format(venv_folder_path, project_folder_path, project_name)
        has_run_migrations_successfully = server_connection.run(run_migration_command)
        if has_run_migrations_successfully.exited != successful_exit_code:
            return False

        return True

    @classmethod
    def generate_assets_collect(cls, server_connection, deploy_settings):
        """Collect all the assets file on static root folder."""
        venv_folder_path = deploy_settings.get('server_venv_path')
        project_folder_path = deploy_settings.get('server_project_path')
        project_name = deploy_settings.get('project_name')
        successful_exit_code = 0

        collect_static_command = '{}/bin/python {}/manage.py collectstatic --settings={}.settings --no-input'.format(venv_folder_path, project_folder_path, project_name)
        has_collect_static = server_connection.run(collect_static_command)
        if has_collect_static.exited != successful_exit_code:
            return False

        return True

    @classmethod
    def run_gunicorn_service(cls, server_connection, deploy_settings):
        """Start gunicorn service."""
        venv_folder_path = deploy_settings.get('server_venv_path')
        project_folder_path = deploy_settings.get('server_project_path')
        pid_file_path = deploy_settings.get('gunicorn_pid_file')
        gunicorn_config_path = '{}/{}'.format(project_folder_path, deploy_settings.get('gunicorn_config_file'))
        successful_exit_code = 0

        get_gunicorn_pid_command = '[ -f {0} ] && cat {0} || echo 0'.format(pid_file_path)
        get_gunicorn_pid_result = server_connection.run(get_gunicorn_pid_command)
        gunicorn_pid_code = int(get_gunicorn_pid_result.stdout)
        if gunicorn_pid_code != 0:
            kill_old_gunicorn_service_command = 'kill -9 {}'.format(gunicorn_pid_code)
            kill_old_gunicorn_service_result = server_connection.run(
                kill_old_gunicorn_service_command, hide=True)
            if kill_old_gunicorn_service_result.exited != 0:
                return False

        project_wsgi_path = '{}.wsgi:application'.format(deploy_settings.get('project_name'))
        init_gunicorn_service_command = 'cd {} && DJANGO_SETTINGS_MODULE={}.settings {}/bin/gunicorn -c {} {}'.format(
            project_folder_path, deploy_settings.get('project_name'), venv_folder_path, gunicorn_config_path, project_wsgi_path)

        init_gunicorn_service_result = server_connection.run(init_gunicorn_service_command)
        if init_gunicorn_service_result.exited != successful_exit_code:
            return False

        return True

    @classmethod
    def check_settings_folder_is_already_exist(cls, settings_folder_path):
        """Check if settings folder is already created."""
        return os.path.exists(settings_folder_path)

    def get_deploy_yaml_config(self, project_root_path):
        """Get configuration from deploy.yml file to dict."""
        project_deploy_yaml_path = '{}/deploy.yml'.format(project_root_path)
        deploy_yaml_object = {}

        with open(project_deploy_yaml_path, 'r') as deploy_yaml_file:
            try:
                deploy_yaml_object = yaml.load(deploy_yaml_file)
            except yaml.YAMLError:
                self.stdout.write('- Error on parsing deploy.yml')

        return deploy_yaml_object

    @classmethod
    def generate_settings_folder(cls, settings_folder_path):
        """Create a new folder."""
        os.makedirs(settings_folder_path)

    def generate_new_settings_file(self, project_config_folder_path, current_dir_path):
        """Generate new settings files called base.py and __init__ in settings folder."""
        settings_folder_path = '{}/settings'.format(project_config_folder_path)
        init_file_for_settings_folder = '{}/settings_init.example.py'.format(current_dir_path)

        shutil.copyfile(init_file_for_settings_folder, '{}/__init__.py'.format(settings_folder_path))
        setting_file_path = '{}/settings.py'.format(project_config_folder_path)
        new_base_setting_file_path = '{}/base.py'.format(settings_folder_path)

        try:
            with open(setting_file_path, 'r') as old_settings, open(new_base_setting_file_path, 'w') as new_settings:
                base_dir_var_name = 'BASE_DIR'
                regex = r'(.*) = (.*)'
                var_position_on_regex = 1

                for line in old_settings:
                    is_var_line = re.match(regex, line, re.M | re.I)
                    if is_var_line and is_var_line.group(var_position_on_regex) == base_dir_var_name:
                        line = self.generate_new_base_dir_path_for_settings() + '\n'
                    new_settings.writelines(line)
        except FileNotFoundError:
            self.stdout.write('- Error creating new file on settings path')
            shutil.rmtree(project_config_folder_path)
            return False
        return True

    @classmethod
    def generate_new_base_dir_path_for_settings(cls):
        """Generate new setting value for BASE_DIR var on setting file."""
        return 'BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))'

    @classmethod
    def generate_environment_files(cls, settings_folder_path):
        """Generate settings files for production and local."""
        setting_base_file_path = '{}/base.py'.format(settings_folder_path)
        shutil.copyfile(setting_base_file_path, '{}/production.py'.format(settings_folder_path))
        shutil.copyfile(setting_base_file_path, '{}/local.py'.format(settings_folder_path))

    @classmethod
    def add_local_settings_to_gitignore(cls, project_root_path, project_name):
        """Add local.py settings to gitignore file."""
        local_setting_file_path = '/{}/settings/local.py'.format(project_name)
        gitignore_file_path = '{}/.gitignore'.format(project_root_path)

        with open(gitignore_file_path, 'a') as gitignore_file:
            gitignore_file.write(local_setting_file_path + '\n')

    @classmethod
    def remove_old_settings_file(cls, project_config_folder_path):
        """Remove old setting file."""
        old_settings_file = '{}/settings.py'.format(project_config_folder_path)
        if os.path.isfile(old_settings_file):
            os.remove(old_settings_file)

    def generate_gunicorn_config_file(self, deploy_settings, project_root_path, current_dir_path):
        """Generate gunicorn settings file."""
        pattern_gunicorn_file_path = '{}/gunicorn.conf.py'
        gunicorn_file_path = pattern_gunicorn_file_path.format(project_root_path)
        gunicorn_file_example_path = pattern_gunicorn_file_path.format(current_dir_path)

        with open(gunicorn_file_example_path, 'r') as gunicorn_settings_example, open(gunicorn_file_path, 'w') as gunicorn_settings:
            regex = r'(.*) = (.*)'
            var_position_on_regex = 1

            for line in gunicorn_settings_example:
                is_var_line = re.match(regex, line, re.M | re.I)
                if is_var_line:
                    var_pattern_name = is_var_line.group(var_position_on_regex)
                    line = self.generate_line_for_replace_gunicorn_file(var_pattern_name, line, deploy_settings)
                gunicorn_settings.writelines(line)

    @classmethod
    def generate_line_for_replace_gunicorn_file(cls, var_pattern_name, processing_line, deploy_settings):
        """Replace lines on gunicorn file from deploy.yml."""
        bind_var_name = 'bind'
        workers_var_name = 'workers'
        worker_class_var_name = 'worker_class'
        pidfile_var_name = 'pidfile'

        if var_pattern_name == bind_var_name:
            settings_value = "'{}'".format(deploy_settings.get('gunicorn_bind'))
        elif var_pattern_name == workers_var_name:
            settings_value = deploy_settings.get('gunicorn_workers')
        elif var_pattern_name == worker_class_var_name:
            settings_value = "'{}'".format(deploy_settings.get('gunicorn_worker_class'))
        elif var_pattern_name == pidfile_var_name:
            settings_value = "'{}'".format(deploy_settings.get('gunicorn_pid_file'))
        else:
            return processing_line

        pattern_assign_var = '{} = {}\n'
        new_line = pattern_assign_var.format(var_pattern_name, settings_value)

        return new_line
