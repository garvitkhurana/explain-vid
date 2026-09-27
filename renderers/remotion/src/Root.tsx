import {Composition, Series} from 'remotion';
import defaultSpec from '../../../specs/semif.json';
import {SceneView, Scene} from './scenes';

// The spec arrives as input props: `remotion render ... --props=../../specs/<name>.json`.
// Studio falls back to semif.json.
type Spec = {meta: {fps: number; size: number[]}; scenes: Scene[]};

const frames = (s: Scene, fps: number) => Math.round(s.duration_s * fps);

const Explainer: React.FC<Spec> = ({meta, scenes}) => (
  <Series>
    {scenes.map((s) => (
      <Series.Sequence key={s.id} durationInFrames={frames(s, meta.fps)}>
        <SceneView scene={s} />
      </Series.Sequence>
    ))}
  </Series>
);

export const RemotionRoot: React.FC = () => (
  <Composition
    id="Explainer"
    component={Explainer}
    defaultProps={defaultSpec as unknown as Spec}
    calculateMetadata={({props}) => ({
      fps: props.meta.fps,
      width: props.meta.size[0],
      height: props.meta.size[1],
      durationInFrames: props.scenes.reduce((n, s) => n + frames(s, props.meta.fps), 0),
    })}
  />
);
