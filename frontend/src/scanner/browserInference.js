import { detectorTensor, classifierTensor, decodeDetections, softmax, assembleBoard } from "./browserMath.js";

export async function inferImage(ort, sessions, image, config) {
  const tensor = new ort.Tensor("float32", detectorTensor(image, config.input_size), [1, 3, config.input_size, config.input_size]);
  let raw;
  let pieces;
  try {
    raw = await sessions.detector.run({ image: tensor });
    pieces = decodeDetections(raw, config, image.width, image.height);
  } finally {
    tensor.dispose();
    Object.values(raw || {}).forEach((value) => value.dispose());
  }
  for (const piece of pieces) {
    const input = new ort.Tensor("float32", classifierTensor(image, piece.box, config.crop), [1, 3, config.crop.size, config.crop.size]);
    let output;
    try {
      output = await sessions.classifier.run({ image: input });
      const probabilities = softmax(Object.values(output)[0].data);
      piece.alternatives = probabilities.map((score, index) => ({ label: config.classes[index + 1], score }))
        .sort((a, b) => b.score - a.score).slice(0, 3);
      piece.class = piece.alternatives[0].label;
      piece.classifierScore = piece.alternatives[0].score;
    } finally {
      input.dispose();
      Object.values(output || {}).forEach((value) => value.dispose());
    }
  }
  return assembleBoard(pieces, image.width, image.height);
}
