import json
import os
import time
from concurrent import futures
from pathlib import Path

import grpc

from config import device_config
from hysia.search.search import DatabasePklSearch
from hysia.utils.logger import Logger
from hysia.utils.perf import StreamSuppressor
from protos import api2msl_pb2, api2msl_pb2_grpc
from utils.misc import obtain_device

_ONE_DAY_IN_SECONDS = 24 * 60 * 60

logger = Logger(
    name='scene_search_model_server',
    severity_levels={'StreamHandler': 'INFO'}
)

video_path = Path(__file__).absolute().parents[1] / 'output/multi_features'


def load_search_machine():
    with StreamSuppressor():
        search_machine = DatabasePklSearch(video_path)
    return search_machine


# Custom request servicer
class Api2MslServicer(api2msl_pb2_grpc.Api2MslServicer):
    def __init__(self):
        super().__init__()

        cuda, device_num = obtain_device(device_config.feature_model_server)

        if cuda:
            os.environ['CUDA_VISIBLE_DEVICES'] = str(device_num)
        else:
            os.environ['CUDA_VISIBLE_DEVICES'] = ''

        logger.info(f'Using {"CUDA:" if cuda else "CPU"}{os.environ["CUDA_VISIBLE_DEVICES"]}')

        self.search_machine = load_search_machine()

    def GetJson(self, request, context):
        meta = json.loads(request.meta)
        img_path = request.buf.decode()
        logger.info('Searching by ' + img_path)
        # Decode image from buf
        with StreamSuppressor():
            results = self.search_machine.search(
                image_query=img_path,
                subtitle_query=meta['text'],
                face_query=None,
                topK=5,
                tv_name=meta['target_videos'][0] if len(meta['target_videos']) else None
                # TODO Currently only support one target video
            )
        # Convert tensor to list to make it serializable
        for res in results:

            # TODO Here has some bugs, json can not accept numpy results
            if not type(res['FEATURE']) == list:
                res['FEATURE'] = res['FEATURE'].tolist()
            try:
                if not type(res['AUDIO_FEATURE']) == list:
                    res['AUDIO_FEATURE'] = res['AUDIO_FEATURE'].tolist()
            except:
                pass

            try:
                if not type(res['SUBTITLE_FEATURE']) == list and not type(res['SUBTITLE_FEATURE']) == str:
                    res['SUBTITLE_FEATURE'] = res['SUBTITLE_FEATURE'].tolist()
            except:
                pass

        return api2msl_pb2.JsonReply(json=json.dumps(results), meta='')


def main():
    # gRPC server configurations
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    api2msl_pb2_grpc.add_Api2MslServicer_to_server(Api2MslServicer(), server)
    server.add_insecure_port('[::]:50053')
    server.start()
    logger.info('Listening on port 50053')
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        logger.info('Shutting down scene search model server')
        server.stop(0)


if __name__ == '__main__':
    main()
