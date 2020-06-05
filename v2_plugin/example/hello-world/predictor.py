from common.endpoints import BaseEndPoints
from common.servicer import BaseServicer


class PredictorServicer(BaseServicer):
    pass


class PredictorEndPoints(BaseEndPoints):
    async def predict(self):
        self.engine.single_predict()

        return {'result': 'hello world!'}
