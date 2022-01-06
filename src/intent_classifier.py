import numpy as np
import time
from tensorflow.python.keras.preprocessing.sequence import pad_sequences

class IntentClassifier:
    def __init__(self,classes,model,tokenizer):
        self.classes = classes
        self.interpreter = model
        self.tokenizer = tokenizer
        # self.label_encoder = label_encoder
        
        self.interpreter.allocate_tensors()
        input_det = self.interpreter.get_input_details()[0]
        output_det = self.interpreter.get_output_details()[0]
        self.input_index = input_det["index"]
        self.output_index = output_det["index"]
        self.input_shape = input_det["shape"]
        self.output_shape = output_det["shape"]
        self.input_dtype = input_det["dtype"]
        self.output_dtype = output_det["dtype"]

    def get_intent(self,text):
        self.test_keras = self.tokenizer.texts_to_sequences([text])
        self.test_keras_sequence = pad_sequences(self.test_keras, maxlen=16, padding='post', dtype='float32')
        self.interpreter.set_tensor(self.input_index, self.test_keras_sequence)
        self.interpreter.invoke()
        self.pred = self.interpreter.get_tensor(self.output_index)[0]
        return self.classes[np.argmax(self.pred,0)]