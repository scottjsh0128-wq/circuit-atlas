import {runModel} from './spec-model.js';
self.onmessage=e=>{try{self.postMessage({result:runModel(e.data,progress=>self.postMessage({progress}))});}catch(error){self.postMessage({error:error.message});}};
