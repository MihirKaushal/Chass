import assert from "node:assert/strict";
import test from "node:test";

import {
  captureScannerPhoto,
  createScannerCameraSession,
} from "./scannerCamera.js";

function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((onResolve, onReject) => {
    resolve = onResolve;
    reject = onReject;
  });
  return { promise, resolve, reject };
}

function cameraStream() {
  let stops = 0;
  const tracks = [
    {
      stop: () => {
        stops += 1;
      },
    },
  ];
  return {
    getTracks: () => tracks,
    get stops() {
      return stops;
    },
  };
}

test("scanner requests video without microphone access and releases it on close", async () => {
  const stream = cameraStream();
  let constraints;
  const session = createScannerCameraSession({
    async getUserMedia(request) {
      constraints = request;
      return stream;
    },
  });

  assert.equal(await session.start(), stream);
  assert.equal(constraints.audio, false);
  assert.equal(constraints.video.facingMode.ideal, "environment");
  assert.equal(stream.stops, 0);
  session.stop();
  session.stop();
  assert.equal(stream.stops, 1);
});

test("a camera granted after cancellation is stopped instead of kept alive", async () => {
  const pending = deferred();
  const stream = cameraStream();
  const session = createScannerCameraSession({
    getUserMedia: () => pending.promise,
  });
  const starting = session.start();

  session.stop();
  pending.resolve(stream);

  assert.equal(await starting, null);
  assert.equal(stream.stops, 1);
});

test("an older permission request cannot replace a newer camera session", async () => {
  const requests = [deferred(), deferred()];
  const oldStream = cameraStream();
  const newStream = cameraStream();
  let index = 0;
  const session = createScannerCameraSession({
    getUserMedia: () => requests[index++].promise,
  });
  const older = session.start();
  const newer = session.start();

  requests[1].resolve(newStream);
  assert.equal(await newer, newStream);
  requests[0].resolve(oldStream);
  assert.equal(await older, null);
  assert.equal(oldStream.stops, 1);
  assert.equal(newStream.stops, 0);
  session.stop();
  assert.equal(newStream.stops, 1);
});

test("reopening the camera releases the previous active stream first", async () => {
  const first = cameraStream();
  const second = cameraStream();
  let index = 0;
  const session = createScannerCameraSession({
    getUserMedia: async () => [first, second][index++],
  });

  assert.equal(await session.start(), first);
  const reopening = session.start();
  assert.equal(first.stops, 1);
  assert.equal(await reopening, second);
  session.stop();
  assert.equal(second.stops, 1);
});

test("camera permission errors remain visible unless the request was cancelled", async () => {
  const denied = Object.assign(new Error("Denied"), {
    name: "NotAllowedError",
  });
  const session = createScannerCameraSession({
    getUserMedia: async () => {
      throw denied;
    },
  });
  await assert.rejects(session.start(), (error) => error === denied);

  const pending = deferred();
  const cancelled = createScannerCameraSession({
    getUserMedia: () => pending.promise,
  });
  const starting = cancelled.start();
  cancelled.stop();
  pending.reject(denied);
  assert.equal(await starting, null);
});

test("capturing before a camera frame exists cannot create an empty photo", async () => {
  await assert.rejects(
    captureScannerPhoto({ readyState: 0, videoWidth: 0, videoHeight: 0 }),
    /still starting/,
  );
});
