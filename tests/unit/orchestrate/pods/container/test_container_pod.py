import os
import time
import pytest

from jina.excepts import RuntimeFailToStart
from jina.parsers import set_pod_parser, set_gateway_parser
from jina.orchestrate.pods.container import ContainerPod

cur_dir = os.path.dirname(os.path.abspath(__file__))


@pytest.fixture(scope='module')
def env_checker_docker_image_built():
    import docker

    client = docker.from_env()
    client.images.build(path=os.path.join(cur_dir, 'env-checker/'), tag='env-checker')
    client.close()
    yield
    time.sleep(2)
    client = docker.from_env()
    client.containers.prune()


def test_container_pod_pass_envs(env_checker_docker_image_built):
    import docker

    with ContainerPod(
        set_pod_parser().parse_args(
            [
                '--uses',
                'docker://env-checker',
                '--env',
                'key1=value1',
                '--env',
                'key2=value2',
            ]
        )
    ) as pod:
        container = pod._container
        status = container.status

    assert status == 'running'
    client = docker.from_env()
    containers = client.containers.list()
    assert container.id not in containers
    with pytest.raises(docker.errors.NotFound):
        pod._container


@pytest.fixture(scope='module')
def fail_start_docker_image_built():
    import docker

    client = docker.from_env()
    client.images.build(path=os.path.join(cur_dir, 'fail-start/'), tag='fail-start')
    client.close()
    yield
    time.sleep(2)
    client = docker.from_env()
    client.containers.prune()


def test_failing_executor(fail_start_docker_image_built):
    import docker

    args = set_pod_parser().parse_args(
        [
            '--uses',
            'docker://fail-start',
        ]
    )

    with pytest.raises(RuntimeFailToStart):
        pod = ContainerPod(args)
        with pod:
            pass

    with pytest.raises(docker.errors.NotFound):
        pod._container


def test_pass_arbitrary_kwargs(monkeypatch, mocker):
    import docker

    mocker.patch(
        'jina.serve.runtimes.asyncio.AsyncNewLoopRuntime.is_ready',
        return_value=True,
    )

    class MockContainers:
        class MockContainer:
            def reload(self):
                pass

            def logs(self, **kwargs):
                return []

            @property
            def id(self):
                return 'mock-id'

            def reload(self):
                pass

            def kill(self, signal, *args):
                assert signal == 'SIGTERM'

        def __init__(self):
            pass

        def list(self):
            return []

        def get(self, *args):
            return MockContainers.MockContainer()

        def run(self, *args, **kwargs):
            assert 'ports' in kwargs
            assert 'environment' in kwargs
            envs = kwargs['environment']
            assert 'JINA_DEPLOYMENT_NAME' in envs
            assert 'VAR1' in envs
            assert envs['VAR1'] == 'BAR'
            assert 'VAR2' in envs
            assert envs['VAR2'] == 'FOO'
            assert 'hello' in kwargs
            assert kwargs['hello'] == 0
            return MockContainers.MockContainer()

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def close(self):
            pass

        def version(self):
            return {'Version': '20.0.1'}

        @property
        def networks(self):
            return {'bridge': None}

        @property
        def containers(self):
            return MockContainers()

        @property
        def images(self):
            return {}

    monkeypatch.setattr(docker, 'from_env', MockClient)
    args = set_pod_parser().parse_args(
        [
            '--uses',
            'docker://jinahub/pod',
            '--env',
            '--env',
            'VAR1=BAR',
            '--env',
            'VAR2=FOO',
            '--docker-kwargs',
            'hello: 0',
        ]
    )
    with ContainerPod(args) as pod:
        pass
    pod.join()
    assert pod.worker.exitcode == 0


@pytest.fixture(scope='module')
def head_runtime_docker_image_built():
    import docker

    client = docker.from_env()
    client.images.build(path=os.path.join(cur_dir, 'head-runtime/'), tag='head-runtime')
    client.close()
    yield
    time.sleep(2)
    client = docker.from_env()
    client.containers.prune()


def test_container_pod_head_runtime(head_runtime_docker_image_built):
    import docker

    with ContainerPod(
        set_pod_parser().parse_args(
            [
                '--uses',
                'docker://head-runtime',
            ]
        )
    ) as pod:
        container = pod._container
        status = pod._container.status

    assert status == 'running'
    client = docker.from_env()
    containers = client.containers.list()
    assert container.id not in containers
    with pytest.raises(docker.errors.NotFound):
        pod._container


@pytest.fixture(scope='module')
def gateway_runtime_docker_image_built():
    import docker

    client = docker.from_env()
    client.images.build(
        path=os.path.join(cur_dir, 'gateway-runtime/'), tag='gateway-runtime'
    )
    client.close()
    yield
    time.sleep(2)
    client = docker.from_env()
    client.containers.prune()


@pytest.mark.skip('ContainerPod is not ready to handle `Gateway`')
@pytest.mark.parametrize('protocol', ['grpc', 'http', 'websocket'])
def test_container_pod_gateway_runtime(protocol, gateway_runtime_docker_image_built):
    import docker

    with ContainerPod(
        set_gateway_parser().parse_args(
            [
                '--uses',
                'docker://gateway-runtime',
                '--graph-description',
                '{"start-gateway": ["pod0"], "pod0": ["end-gateway"]}',
                '--deployments-addresses',
                '{"pod0": ["0.0.0.0:1234"]}',
                '--protocol',
                protocol,
            ]
        )
    ) as pod:
        container = pod._container
        status = pod._container.status

    assert status == 'running'
    client = docker.from_env()
    containers = client.containers.list()
    assert container.id not in containers
    with pytest.raises(docker.errors.NotFound):
        pod._container
