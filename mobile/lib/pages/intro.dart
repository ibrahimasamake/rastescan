import 'dart:async';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

/// The film that opens the app: a real pothole, the AI scan, the app, the name. It plays over Home each time the app starts and
/// can always be skipped. It never holds the app back: if the video fails or is slow to start, Home simply appears.
class IntroFilm extends StatefulWidget {
  const IntroFilm({super.key});
  @override
  State<IntroFilm> createState() => _IntroFilmState();
}

class _IntroFilmState extends State<IntroFilm> {
  static const startWithin = Duration(seconds: 4);
  static const fade = Duration(milliseconds: 500);

  VideoPlayerController? _video;
  Timer? _timer;
  bool _ready = false, _leaving = false, _gone = false;

  @override
  void initState() {
    super.initState();
    // The phone's "reduce motion" setting: go straight to Home.
    if (WidgetsBinding.instance.platformDispatcher.accessibilityFeatures.disableAnimations) {
      _gone = true;
      return;
    }
    _start();
  }

  Future<void> _start() async {
    _timer = Timer(startWithin, () {
      if (!_ready) _finish();
    });
    // mixWithOthers: a silent film must not stop the music someone is listening to.
    final c = VideoPlayerController.asset('assets/rastescan-intro.mp4', videoPlayerOptions: VideoPlayerOptions(mixWithOthers: true));
    _video = c;
    try {
      await c.initialize();
      if (!mounted || _leaving || _gone) return;
      await c.setVolume(0);
      c.addListener(_watch);
      await c.play();
      if (!mounted) return;
      setState(() => _ready = true);
      // Also ends the film if playback stalls and never reports reaching the end.
      _timer?.cancel();
      _timer = Timer(c.value.duration + const Duration(seconds: 3), _finish);
    } catch (_) {
      _finish();
    }
  }

  void _watch() {
    final v = _video?.value;
    if (v == null) return;
    if (v.hasError || (v.isInitialized && v.position >= v.duration)) _finish();
  }

  void _finish() {
    if (!mounted || _leaving || _gone) return;
    _timer?.cancel();
    setState(() => _leaving = true);
  }

  @override
  void dispose() {
    _timer?.cancel();
    _video?.removeListener(_watch);
    _video?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_gone) return const SizedBox.shrink();
    final c = _video;
    return IgnorePointer(
      ignoring: _leaving,
      child: AnimatedOpacity(
        opacity: _leaving ? 0 : 1,
        duration: fade,
        onEnd: () {
          if (!_leaving || !mounted) return;
          setState(() => _gone = true);
          _video?.removeListener(_watch);
          _video?.dispose();
          _video = null;
        },
        child: ColoredBox(
          color: Colors.black,
          child: Stack(fit: StackFit.expand, children: [
            // The film is wide and its name card spans the frame, so it is fitted whole rather than cropped on a tall phone.
            if (_ready && c != null) Center(child: AspectRatio(aspectRatio: c.value.aspectRatio, child: VideoPlayer(c))),
            SafeArea(
              child: Align(
                alignment: Alignment.topRight,
                child: Padding(
                  padding: const EdgeInsets.all(12),
                  child: TextButton(
                    onPressed: _finish,
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.white,
                      backgroundColor: Colors.black45,
                      minimumSize: const Size(0, 44),
                      padding: const EdgeInsets.symmetric(horizontal: 18),
                      shape: StadiumBorder(side: BorderSide(color: Colors.white.withValues(alpha: .45))),
                      textStyle: const TextStyle(fontWeight: FontWeight.w700),
                    ),
                    child: const Text('Skip intro'),
                  ),
                ),
              ),
            ),
          ]),
        ),
      ),
    );
  }
}
