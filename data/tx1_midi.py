#import DLProject.DataAcquisitonAndAnalysis.music_analysis_scripts.midi_analyzer.py
from collections import defaultdict
import tempfile



def midi_to_tx1(midi):
  import pretty_midi
  pretty_midi.pretty_midi.MAX_TICK = 1e16

  # Load MIDI file
  with tempfile.NamedTemporaryFile('wb') as mf:
    mf.write(midi)
    mf.seek(0)
    midi = pretty_midi.PrettyMIDI(mf.name)

  ins_names = ['AGP','AB','TP','EGJ','AS','TS','TB',]

  instruments = sorted(midi.instruments, key=lambda x: ins_names.index(x.name))
  samp_to_events = defaultdict(list)
  for ins in instruments:
    instag = ins.name.upper()

    last_start = -1
    last_end = -1
    last_pitch = -1
    for note in ins.notes:
      start = (note.start * 44100) + 1e-6
      end = (note.end * 44100) + 1e-6

      #assert start - int(start) < 1e-3
      #assert end - int(end) < 1e-3

      start = int(start)
      end = int(end)

      #assert start > last_start
      #assert start >= last_end

      pitch = note.pitch

      if last_end >= 0 and last_end != start:
        samp_to_events[last_end].append('{}_NOTEOFF'.format(instag))
      samp_to_events[start].append('{}_NOTEON_{}'.format(instag, pitch))

      last_start = start
      last_end = end
      last_pitch = pitch

    if last_pitch != -1:
      samp_to_events[last_end].append('{}_NOTEOFF'.format(instag))

  tx1 = []
  last_samp = 0
  for samp, events in sorted(samp_to_events.items(), key=lambda x: x[0]):
    wt = samp - last_samp
    assert last_samp == 0 or wt > 0
    if wt > 0:
      tx1.append('WT_{}'.format(wt))
    tx1.extend(events)
    last_samp = samp

  nsamps = int((midi.time_signature_changes[-1].time * 44100) + 1e-6)
  if nsamps > last_samp:
    tx1.append('WT_{}'.format(nsamps - last_samp))

  tx1 = '\n'.join(tx1)
  return tx1


def tx1_to_midi(tx1):
  import pretty_midi

  tx1 = tx1.strip().splitlines()
  nsamps = sum([int(x.split('_')[1]) for x in tx1 if x[:2] == 'WT'])

  CHANNELS_TO_NEW_NAMES = {
    65: 'AS',
    11: 'VP',
    4: 'EP',
    0: 'AGP',
    35: 'FB',
    40: 'VO',
    32: 'AB',
}

  # Create MIDI instruments
  name_to_ins = {}
  name_to_pitch = {}
  name_to_start = {}
  for program in CHANNELS_TO_NEW_NAMES:
    noun = CHANNELS_TO_NEW_NAMES[program]
    instr = pretty_midi.Instrument(program=program, name=noun, is_drum=False)
    name_to_ins[noun] = instr
    name_to_pitch[noun] = None
    name_to_start[noun] = None

  samp = 0
  for event in tx1:
    if event[:2] == 'WT':
      samp += int(event[3:])
    else:
      tokens = event.split('_')
      name = tokens[0]
      ins = name_to_ins[tokens[0]]

      old_pitch = name_to_pitch[name]
      if tokens[1] == 'NOTEON':
        if old_pitch is not None:
          ins.notes.append(pretty_midi.Note(
              velocity=55,
              pitch=old_pitch,
              start=name_to_start[name] / 44100.,
              end=samp / 44100.))
        name_to_pitch[name] = int(tokens[2])
        name_to_start[name] = samp
      else:
        if old_pitch is not None:
          ins.notes.append(pretty_midi.Note(
              velocity=45,
              pitch=name_to_pitch[name],
              start=name_to_start[name] / 44100.,
              end=samp / 44100.))

        name_to_pitch[name] = None
        name_to_start[name] = None

  # Deactivating this for generated files
  #for name, pitch in name_to_pitch.items():
  #  assert pitch is None

  # Create MIDI and add instruments
  midi = pretty_midi.PrettyMIDI(initial_tempo=120, resolution=22050)
  midi.instruments.extend(name_to_ins.values())

  # Create indicator for end of song
  eos = pretty_midi.TimeSignature(1, 1, nsamps / 44100.)
  midi.time_signature_changes.append(eos)

  with tempfile.NamedTemporaryFile('rb') as mf:
    midi.write(mf.name)
    midi = mf.read()

  return midi
