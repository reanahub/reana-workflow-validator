# -*- coding: utf-8 -*-
#
# This file is part of REANA.
# Copyright (C) 2018, 2019, 2020, 2021, 2022, 2024 CERN.
#
# REANA is free software; you can redistribute it and/or modify it
# under the terms of the MIT License; see LICENSE file for more details.

import os

from typing import Dict, List, Optional

from reana_commons.config import (
    REANA_DEFAULT_SNAKEMAKE_ENV_IMAGE,
    COMMAND_DANGEROUS_OPERATIONS,
    WORKFLOW_RUNTIME_USER_GID,
    WORKFLOW_RUNTIME_USER_UID,
)
from reana_commons.validation.utils import validate_reana_yaml, validate_workspace
from reana_commons.validation.operational_options import validate_operational_options
from reana_commons.validation.parameters import build_parameters_validator
from reana_commons.errors import REANAValidationError
from reana_commons.validation.compute_backends import build_compute_backends_validator

import requests
import json
import yaml
import json

def workflow_validation():

    # Get workspace mount path in order to read reana.yaml
    workspace_mount_path = os.environ['workspace_mount_path']

    # Harcoded Example
    # reana_yaml = {'inputs': {'files': ['code/helloworld.py', 'data/names.txt'], 'parameters': {'helloworld': 'code/helloworld.py', 'inputfile': 'data/names.txt', 'outputfile': 'results/greetings.txt', 'sleeptime': 0}}, 'outputs': {'files': ['results/greetings.txt']}, 'runtime_parameters': False, 'server_capabilities': False, 'skip_validate_environments': True, 'version': '0.3.0', 'workflow': {'specification': {'steps': [{'commands': ['sleep 666666666666666'], 'environment': 'docker.io/impidio/urootshell:0.4'}]}, 'type': 'serial'}}
    
    reana_yaml = open(workspace_mount_path + "/reana.yaml", 'r').read()  # FIXME: get the path of workspace correctly, currently there is the workspace path along with some extra fields
    print("Received:")
    print(reana_yaml)

    server_capabilities = []

    if "server_capabilities" in reana_yaml and (reana_yaml['server_capabilities'] != False):
      print("Validating server capabilities")
      server_capabilities = validate_server_capabilities(reana_yaml)
      print(server_capabilities)

    # delete server_capabilities section as it is no longer needed
    del reana_yaml['server_capabilities']


    runtime_params_warnings = []
    runtime_params_errors = []

    # If runtime parameters exist, get them
    if "runtime_parameters" in reana_yaml and (reana_yaml['runtime_parameters'] != False):
      runtime_parameters = reana_yaml['runtime_parameters']
      print("runtime_parameters")
      print(runtime_parameters)

      # Check for dangerous operations
      for parameter in runtime_parameters:
        for dangerous_command in COMMAND_DANGEROUS_OPERATIONS:
          if dangerous_command in runtime_parameters[parameter]:
            runtime_params_warnings.append('Operation "' + runtime_parameters[parameter] + '" might be dangerous.')

      # Check if a runtime parameter already exists in the provided reana_yaml
      parameters_in_yaml = []
      for parameter_name in reana_yaml["inputs"]["parameters"]:
          parameters_in_yaml.append(parameter_name)
      
      for parameter in runtime_parameters:
          if parameter not in parameters_in_yaml:
            runtime_params_errors.append('Command-line parameter "' + parameter + '" is not defined in reana.yaml.')
          
      print("runtime_params_warnings")
      print(runtime_params_warnings)

    # delete runtime parameters as they are no longer needed
    del reana_yaml['runtime_parameters']


    environments_warnings = []

    if "skip_validate_environments" in reana_yaml and (reana_yaml['skip_validate_environments'] == False):
      print("validate_environments_results")
      environments_warnings = validate_environment(reana_yaml)
      print(environments_warnings)

    # delete skip_validate_environments section as it is no longer needed
    del reana_yaml['skip_validate_environments']


    try:
        reana_spec_file_warnings = validate_reana_yaml(reana_yaml)
    except Exception as e:
        return json.dumps({"message":str(e), "status":"400"})

    """Validate REANA specification file."""
    if "options" in reana_yaml.get("inputs", {}):
        workflow_type = reana_yaml["workflow"]["type"]
        workflow_options = reana_yaml["inputs"]["options"]
        try:
            validate_operational_options(workflow_type, workflow_options)
        except Exception as e:
            return json.dumps(message=str(e), status="400")

    """Validate parameters."""
    reana_spec_params_warnings = None
    try:
        reana_spec_params_warnings = validate_parameters(reana_yaml)
    except Exception as e:
        return json.dumps({"message":str(e), "status":"400"})

    response = {"reana_spec_file_warnings": reana_spec_file_warnings, 
                "reana_spec_params_warnings": json.dumps(vars(reana_spec_params_warnings), default=list),
                "runtime_params_warnings": runtime_params_warnings,
                "runtime_params_errors": runtime_params_errors,
                "server_capabilities": server_capabilities,
                "environments_warnings": environments_warnings}

    print("Sending Response:")
    print(response)

    # Output results to a file
    reana_validation_results = open(workspace_mount_path + "/reana_validation_results.json", "w")
    reana_validation_results.writelines(response)
    reana_validation_results.close()

    # Serializing json
    json_object = json.dumps(response, indent=4)
    
    # Writing to sample.json
    with open("reana_results.json", "w") as outfile:
        outfile.write(json_object)

    return json.dumps({"message":response, "status":"200"})

def validate_parameters(reana_yaml: Dict) -> None:
    """Validate the presence of input parameters in workflow step commands and viceversa.

    :param reana_yaml: REANA YAML specification.
    """

    validator = build_parameters_validator(reana_yaml)
    try:
        validator.validate_parameters()
        return validator
    except REANAValidationError as e:
        raise e

def validate_server_capabilities(reana_yaml: Dict) -> None:
    """Validate server capabilities in REANA specification file.

    :param reana_yaml: dictionary which represents REANA specification file.
    """

    validation_results = []
    supported_backends = os.environ.get('REANA_COMPUTE_BACKENDS', None)
    validation_results.append(validate_compute_backends(reana_yaml, supported_backends))

    root_path = reana_yaml.get("workspace", {}).get("root_path")
    available_workspaces = os.environ.get('WORKSPACE_PATHS', None)
    validation_results.append(validate_available_workspace(root_path, available_workspaces))

    return validation_results

def validate_compute_backends(
    reana_yaml: Dict, supported_backends: Optional[List[str]]
) -> None:
    """Validate compute backends in REANA specification file according to workflow type.

    :param reana_yaml: dictionary which represents REANA specification file.
    :param supported_backends: a list of the supported compute backends.
    """

    validator = build_compute_backends_validator(reana_yaml, supported_backends)
    try:
        validator.validate()
    except REANAValidationError as e:
        return {"message": str(e), "msg_type": "error"}

    return {"message": "Workflow compute backends appear to be valid.", "msg_type": "success"}

def validate_available_workspace(
    root_path: str, available_workspaces: Optional[List[str]]
) -> None:
    """Validate workspace in REANA specification file.

    :param root_path: workspace root path to be validated.
    :param available_workspaces: a list of the available workspaces.

    :raises ValidationError: Given workspace in REANA spec file does not validate against
        allowed workspaces.
    """
    if root_path:
        try:
            validate_workspace(root_path, available_workspaces)
            return {"message": "Workflow workspace appears valid.", "msg_type": "success"}
        except REANAValidationError as e:
            return {"message": str(e), "msg_type": "error"}

# Environment validation parts 

def validate_environment(reana_yaml, pull=False):
    """Validate environments in REANA specification file according to workflow type.

    :param reana_yaml: Dictionary which represents REANA specification file.
    :param pull: If true, attempt to pull remote environment image to perform GID/UID validation.
    """

    def build_validator(workflow):
        workflow_type = workflow["type"]
        if workflow_type == "serial":
            workflow_steps = workflow["specification"]["steps"]
            return EnvironmentValidatorSerial(workflow_steps=workflow_steps, pull=pull)
        if workflow_type == "yadage":
            workflow_steps = workflow["specification"]["stages"]
            return EnvironmentValidatorYadage(workflow_steps=workflow_steps, pull=pull)
        if workflow_type == "cwl":
            workflow_steps = workflow.get("specification", {}).get("$graph", workflow)
            return EnvironmentValidatorCWL(workflow_steps=workflow_steps, pull=pull)
        if workflow_type == "snakemake":
            workflow_steps = workflow["specification"]["steps"]
            return EnvironmentValidatorSnakemake(
                workflow_steps=workflow_steps, pull=pull
            )

    workflow = reana_yaml["workflow"]
    validator = build_validator(workflow)
    messages = validator.validate()
    return messages


DOCKER_REGISTRY_INDEX_URL = (
    "https://hub.docker.com/v2/repositories/{repository}{image}/tags/{tag}"
)
"""Docker Hub registry index URL."""

DOCKER_REGISTRY_PREFIX = "docker.io"
"""Prefix for DockerHub image registry."""

ENVIRONMENT_IMAGE_SUSPECTED_TAGS_VALIDATOR = ["latest", "master", ""]
"""Warns user if above environment image tags are used."""

GITLAB_CERN_REGISTRY_INDEX_URL = (
    "https://gitlab.cern.ch/api/v4/projects/{image}/registry/repositories?tags=1"
)
"""GitLab CERN registry index URL."""

GITLAB_CERN_REGISTRY_PREFIX = "gitlab-registry.cern.ch"
"""Prefix for GitLab image registry at CERN."""

class EnvironmentValidationError(Exception):
    """REANA workflow environment validation didn't succeed."""

class EnvironmentValidatorBase:
    """REANA workflow environments validation base class."""

    def __init__(self, workflow_steps=None, pull=False):
        """Validate environments in REANA workflow.

        :param workflow_steps: List of dictionaries which represents different steps involved in workflow.
        :param pull: If true, attempt to pull remote environment image to perform GID/UID validation.
        """
        self.workflow_steps = workflow_steps
        self.pull = pull
        self.validated_images = set()
        self.messages = []

    def validate(self):
        """Validate REANA workflow environments."""
        try:
            self.validate_environment()
        except EnvironmentValidationError as e:
            self.messages.append({"type": "error", "message": str(e)})

        return self.messages

    def validate_environment(self):
        """Validate environments in REANA workflow."""
        raise NotImplementedError

    def _validate_environment_image(self, image, kubernetes_uid=None):
        """Validate image environment.

        :param image: Full image name with tag if specified.
        :param kubernetes_uid: Kubernetes UID defined in workflow spec.
        """

        if image not in self.validated_images:
            image_name, image_tag = self._validate_image_tag(image)
            exists_locally, _ = self._image_exists(image_name, image_tag)
            if exists_locally or self.pull:
                uid, gids = self._get_image_uid_gids(image_name, image_tag)
                self._validate_uid_gids(uid, gids, kubernetes_uid=kubernetes_uid)
            else:
                self.messages.append(
                    {
                        "type": "warning",
                        "message": "UID/GIDs validation skipped, specify `--pull` to enable it.",
                    }
                )
            self.validated_images.add(image)

    def _image_exists(self, image, tag):
        """Verify if image exists locally or remotely.

        :returns: A tuple with two boolean values: image exists locally, image exists remotely.
        """

        image_exists_remotely = (
            self._image_exists_in_gitlab_cern
            if image.startswith(GITLAB_CERN_REGISTRY_PREFIX)
            else self._image_exists_in_dockerhub
        )

        exists_locally = self._image_exists_locally(image, tag)
        exists_remotely = image_exists_remotely(image, tag)

        if not any([exists_locally, exists_remotely]):
            raise EnvironmentValidationError(
                "Environment image {} does not exist locally or remotely.".format(
                    self._get_full_image_name(image, tag)
                )
            )
        return exists_locally, exists_remotely

    def _validate_uid_gids(self, uid, gids, kubernetes_uid=None):
        """Check whether container UID and GIDs are valid."""
        if WORKFLOW_RUNTIME_USER_GID not in gids:
            if kubernetes_uid is None:
                raise EnvironmentValidationError(
                    "Environment image GID must be {}. GIDs {} were found.".format(
                        WORKFLOW_RUNTIME_USER_GID, gids
                    )
                )
            else:
                self.messages.append(
                    {
                        "type": "warning",
                        "message": "Environment image GID is recommended to be {}. GIDs {} were found.".format(
                            WORKFLOW_RUNTIME_USER_GID, gids
                        ),
                    }
                )
        if kubernetes_uid is not None:
            if kubernetes_uid != uid:
                self.messages.append(
                    {
                        "type": "warning",
                        "message": "`kubernetes_uid` set to {}. UID {} was found.".format(
                            kubernetes_uid, uid
                        ),
                    }
                )
        elif uid != WORKFLOW_RUNTIME_USER_UID:
            self.messages.append(
                {
                    "type": "info",
                    "message": "Environment image uses UID {} but will run as UID {}.".format(
                        uid, WORKFLOW_RUNTIME_USER_UID
                    ),
                }
            )

    def _validate_image_tag(self, image):
        """Validate if image tag is valid."""
        image_name, image_tag = "", ""
        message = {
            "type": "success",
            "message": "Environment image {} has the correct format.".format(image),
        }
        if " " in image:
            raise EnvironmentValidationError(
                f"Environment image '{image}' contains illegal characters."
            )
        if ":" in image:
            environment = image.split(":", 1)
            image_name, image_tag = environment[0], environment[-1]
            if ":" in image_tag:
                raise EnvironmentValidationError(
                    "Environment image {} has invalid tag '{}'".format(
                        image_name, image_tag
                    )
                )
            elif image_tag in ENVIRONMENT_IMAGE_SUSPECTED_TAGS_VALIDATOR:
                message = {
                    "type": "warning",
                    "message": "Using '{}' tag is not recommended in {} environment image.".format(
                        image_tag, image_name
                    ),
                }
        else:
            message = {
                "type": "warning",
                "message": "Environment image {} does not have an explicit tag.".format(
                    image
                ),
            }
            image_name = image

        self.messages.append(message)
        return image_name, image_tag

    def _image_exists_locally(self, image, tag):
        """Verify if image exists locally."""
        full_image = self._get_full_image_name(image, tag or "latest")
        #image_id = run_command(
        #    f'docker images -q "{full_image}"', display=False, return_output=True
        #)
        image_id = False
        # TODO: replace above line with the commented out lines above when sandbox gets implemented
        if image_id:
            self.messages.append(
                {
                    "type": "success",
                    "message": f"Environment image {full_image} exists locally.",
                }
            )
            return True
        else:
            self.messages.append(
                {
                    "type": "warning",
                    "message": f"Environment image {full_image} does not exist locally.",
                }
            )
            return False

    def _image_exists_in_gitlab_cern(self, image, tag):
        """Verify if image exists in GitLab CERN."""
        # Remove registry prefix
        prefixed_image = image
        full_prefixed_image = self._get_full_image_name(image, tag or "latest")
        image = image.split("/", 1)[-1]
        # Encode image name slashes
        remote_registry_url = GITLAB_CERN_REGISTRY_INDEX_URL.format(
            image=requests.utils.quote(image, safe="")
        )
        try:
            # FIXME: if image is private we can't access it, we'd
            # need to pass a GitLab API token generated from the UI.
            response = requests.get(remote_registry_url)
        except requests.exceptions.RequestException as e:
            print(str(e))
            self.messages.append(
                {
                    "type": "error",
                    "message": "Something went wrong when querying {}".format(
                        remote_registry_url
                    ),
                }
            )
            return False

        if not response.ok:
            msg = response.json().get("message")
            self.messages.append(
                {
                    "type": "warning",
                    "message": "Existence of environment image {} in GitLab CERN could not be verified: {}".format(
                        self._get_full_image_name(prefixed_image, tag), msg
                    ),
                }
            )
            return False
        else:
            # If not tag was set, use `latest` (default) to verify.
            tag = tag or "latest"
            tag_exists = any(
                tag_dict["name"] == tag for tag_dict in response.json()[0].get("tags")
            )
            if tag_exists:
                self.messages.append(
                    {
                        "type": "success",
                        "message": "Environment image {} exists in GitLab CERN.".format(
                            full_prefixed_image
                        ),
                    }
                )
                return True
            else:
                self.messages.append(
                    {
                        "type": "warning",
                        "message": 'Environment image {} in GitLab CERN does not exist: Tag "{}" missing.'.format(
                            full_prefixed_image, tag
                        ),
                    }
                )
                return False

    def _image_exists_in_dockerhub(self, image, tag):
        """Verify if image exists in DockerHub."""
        full_image = self._get_full_image_name(image, tag or "latest")
        # remove leading `docker.io/` prefix, if present
        dockerhub_prefix = f"{DOCKER_REGISTRY_PREFIX}/"
        if image.startswith(dockerhub_prefix):
            image = image[len(dockerhub_prefix) :]
        # Some images like `python:2.7-slim` require to specify `library`
        # as a repository in order to work with DockerHub API v2
        repository = "" if "/" in image else "library/"
        docker_registry_url = DOCKER_REGISTRY_INDEX_URL.format(
            repository=repository, image=image, tag=tag
        )
        # Remove traling slash if no tag was specified
        if not tag:
            docker_registry_url = docker_registry_url[:-1]
        try:
            response = requests.get(docker_registry_url)
        except requests.exceptions.RequestException as e:
            print(str(e))
            self.messages.append(
                {
                    "type": "error",
                    "message": "Something went wrong when querying {}".format(
                        docker_registry_url
                    ),
                }
            )
            return False

        if not response.ok:
            if response.status_code == 404:
                msg = response.json().get("message")
                self.messages.append(
                    {
                        "type": "warning",
                        "message": "Environment image {} does not exist in Docker Hub: {}".format(
                            full_image, msg
                        ),
                    }
                )
                return False
            else:
                self.messages.append(
                    {
                        "type": "warning",
                        "message": "==> WARNING: Existence of environment image {} in Docker Hub could not be verified. Status code: {} {}".format(
                            full_image,
                            response.status_code,
                            response.reason,
                        ),
                    }
                )
                return False
        else:
            self.messages.append(
                {
                    "type": "success",
                    "message": "Environment image {} exists in Docker Hub.".format(
                        full_image
                    ),
                }
            )
            return True

    def _get_image_uid_gids(self, image, tag):
        """Obtain environment image UID and GIDs.

        :returns: A tuple with UID and GIDs.
        """
        return 1000, 0
        # TODO: remove the above line when sandbox gets implemented

        from reana_commons.utils import run_command

        # Check if docker is installed.
        run_command("docker version", display=False, return_output=True)
        # Run ``id``` command inside the container.
        uid_gid_output = run_command(
            f'docker run -i -t --rm --entrypoint /bin/sh {self._get_full_image_name(image, tag)} -c "/usr/bin/id -u && /usr/bin/id -G"',
            display=False,
            return_output=True,
        )
        ids = uid_gid_output.splitlines()
        uid, gids = (
            int(ids[-2]),
            [int(gid) for gid in ids[-1].split()],
        )
        return uid, gids

    def _get_full_image_name(self, image, tag=None):
        """Return full image name with tag if is passed."""
        return "{}{}".format(image, ":{}".format(tag) if tag else "")


class EnvironmentValidatorSerial(EnvironmentValidatorBase):
    """REANA serial workflow environments validation."""

    def validate_environment(self):
        """Validate environments in REANA serial workflow."""
        for step in self.workflow_steps:
            image = step["environment"]
            kubernetes_uid = step.get("kubernetes_uid")
            self._validate_environment_image(image, kubernetes_uid=kubernetes_uid)


class EnvironmentValidatorYadage(EnvironmentValidatorBase):
    """REANA yadage workflow environments validation."""

    def _extract_steps_environments(self):
        """Extract environments yadage workflow steps."""

        def traverse_yadage_workflow(stages):
            environments = []
            for stage in stages:
                if "workflow" in stage["scheduler"]:
                    nested_stages = stage["scheduler"]["workflow"].get("stages", {})
                    environments += traverse_yadage_workflow(nested_stages)
                else:
                    environments.append(stage["scheduler"]["step"]["environment"])
            return environments

        return traverse_yadage_workflow(self.workflow_steps)

    def validate_environment(self):
        """Validate environments in REANA yadage workflow."""

        def _check_environment(environment):
            image = "{}{}".format(
                environment["image"],
                (
                    ":{}".format(environment["imagetag"])
                    if "imagetag" in environment
                    else ""
                ),
            )
            k8s_uid = next(
                (
                    resource["kubernetes_uid"]
                    for resource in environment.get("resources", [])
                    if "kubernetes_uid" in resource
                ),
                None,
            )
            self._validate_environment_image(image, kubernetes_uid=k8s_uid)

        steps_environments = self._extract_steps_environments()
        for environment in steps_environments:
            if environment["environment_type"] != "docker-encapsulated":
                raise EnvironmentValidationError(
                    'The only Yadage environment type supported is "docker-encapsulated". Found "{}".'.format(
                        environment["environment_type"]
                    )
                )
            else:
                _check_environment(environment)


class EnvironmentValidatorCWL(EnvironmentValidatorBase):
    """REANA CWL workflow environments validation."""

    def validate_environment(self):
        """Validate environments in REANA CWL workflow."""

        def _validate_workflow_environment(workflow_steps):
            """Validate environments in REANA CWL workflow steps."""
            requirements = workflow_steps.get("requirements", [])
            images = list(filter(lambda req: "dockerPull" in req, requirements))

            for image in images:
                self._validate_environment_image(image["dockerPull"])

        workflow = self.workflow_steps
        if isinstance(workflow, dict):
            _validate_workflow_environment(workflow)
        elif isinstance(workflow, list):
            for wf in workflow:
                _validate_workflow_environment(wf)


class EnvironmentValidatorSnakemake(EnvironmentValidatorBase):
    """REANA Snakemake workflow environments validation."""

    def validate_environment(self):
        """Validate environments in REANA Snakemake workflow."""
        for step in self.workflow_steps:
            image = step["environment"]
            if not image:
                self.messages.append(
                    {
                        "type": "warning",
                        "message": f"Environment image not specified, using {REANA_DEFAULT_SNAKEMAKE_ENV_IMAGE}.",
                    }
                )
                image = REANA_DEFAULT_SNAKEMAKE_ENV_IMAGE
            kubernetes_uid = step.get("kubernetes_uid")
            self._validate_environment_image(image, kubernetes_uid=kubernetes_uid)
  
workflow_validation()