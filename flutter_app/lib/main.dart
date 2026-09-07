// TRUCK-A-FY — Flutter front end for the truckafy-engine Cloud Run service.
//
// Screen 1 "The Arena": scoreboard text box, EXTREMEMETER, Arena Intro switch,
// voice picker, the big red caution-striped MONSTER-FY button, flame-bar
// visualizer while playing, and a cassette-style transport with Share.
//
// Set API_URL at build time:
//   flutter run --dart-define=API_URL=https://truckafy-engine-xxxx-uc.a.run.app
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

const String kApiBase = String.fromEnvironment(
  'API_URL',
  defaultValue: 'https://truckafy-engine-363682438916.us-central1.run.app',
);

// Optional shared secret (must match APP_SECRET on the service):
//   --dart-define=APP_KEY=...
const String kAppKey = String.fromEnvironment('APP_KEY', defaultValue: '');

const List<String> kIntros = [
  'THIS SUNDAY AT THE DOME!',
  'ONE NIGHT ONLY! BE THERE OR BE SQUARE!',
  'BEWARE! BEWARE! BEWARE!',
  'KIDS SEATS ARE STILL FIVE BUCKS!',
];

const Map<String, String> kVoices = {
  'Algenib': 'Gravelly (default)',
  'Fenrir': 'Excitable',
  'Charon': 'Deep',
  'Orus': 'Firm',
  'Puck': 'Upbeat',
};

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setPreferredOrientations([DeviceOrientation.portraitUp]);
  runApp(const TruckafyApp());
}

class TruckafyApp extends StatelessWidget {
  const TruckafyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'TRUCK-A-FY',
      debugShowCheckedModeBanner: false,
      theme: ThemeData.dark(useMaterial3: true).copyWith(
        scaffoldBackgroundColor: const Color(0xFF0B0B0B),
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFFD600),
          secondary: Color(0xFFFF1F1F),
          surface: Color(0xFF161616),
        ),
      ),
      home: const ArenaScreen(),
    );
  }
}

class ArenaScreen extends StatefulWidget {
  const ArenaScreen({super.key});
  @override
  State<ArenaScreen> createState() => _ArenaScreenState();
}

class _ArenaScreenState extends State<ArenaScreen>
    with TickerProviderStateMixin {
  final _text = TextEditingController();
  final _player = AudioPlayer();
  final _rng = Random();

  bool _arenaPrefix = true;
  int _intro = 0;
  double _intensity = 0.85;
  String _voice = 'Algenib';
  bool _loading = false;
  bool _playing = false;
  File? _lastClip;
  String _status = 'READY.';

  late final AnimationController _shake =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 500));
  late final AnimationController _bars =
      AnimationController(vsync: this, duration: const Duration(milliseconds: 120))
        ..addListener(() => setState(() {}));

  @override
  void initState() {
    super.initState();
    _player.playerStateStream.listen((s) {
      final playing = s.playing && s.processingState != ProcessingState.completed;
      if (playing != _playing) {
        setState(() => _playing = playing);
        playing ? _bars.repeat(reverse: true) : _bars.stop();
      }
    });
  }

  @override
  void dispose() {
    _player.dispose();
    _shake.dispose();
    _bars.dispose();
    _text.dispose();
    super.dispose();
  }

  Future<void> _monsterfy() async {
    final msg = _text.text.trim();
    if (msg.isEmpty) return;
    HapticFeedback.heavyImpact();
    setState(() {
      _loading = true;
      _status = 'CALLING THE ANNOUNCER...';
    });
    try {
      final resp = await http
          .post(
            Uri.parse('$kApiBase/truckafy'),
            headers: {
              'Content-Type': 'application/json',
              if (kAppKey.isNotEmpty) 'X-Truckafy-Key': kAppKey,
            },
            body: jsonEncode({
              'text': msg,
              'arena_prefix': _arenaPrefix,
              'intro': _intro,
              'intensity': _intensity,
              'voice': _voice,
            }),
          )
          .timeout(const Duration(seconds: 120));
      if (resp.statusCode != 200) {
        String err = 'HTTP ${resp.statusCode}';
        try {
          err = jsonDecode(resp.body)['error'] ?? err;
        } catch (_) {}
        throw Exception(err);
      }
      final dir = await getTemporaryDirectory();
      final f = File('${dir.path}/truckafy_${DateTime.now().millisecondsSinceEpoch}.mp3');
      await f.writeAsBytes(resp.bodyBytes);
      _lastClip = f;
      await _player.setFilePath(f.path);
      _shake.forward(from: 0);
      HapticFeedback.vibrate();
      setState(() => _status = 'SUNDAY! SUNDAY! SUNDAY!');
      _player.play();
    } catch (e) {
      setState(() => _status = 'ENGINE STALLED: $e');
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _share() async {
    final f = _lastClip;
    if (f == null) return;
    await Share.shareXFiles([XFile(f.path, mimeType: 'audio/mpeg')],
        text: _text.text.trim());
  }

  @override
  Widget build(BuildContext context) {
    final yellow = Theme.of(context).colorScheme.primary;
    return Scaffold(
      body: SafeArea(
        child: AnimatedBuilder(
          animation: _shake,
          builder: (context, child) {
            final t = _shake.value;
            final amp = (1 - t) * 10;
            return Transform.translate(
              offset: Offset(sin(t * 40) * amp, cos(t * 33) * amp * .5),
              child: child,
            );
          },
          child: ListView(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            children: [
              _ChromeHeader(playing: _playing, level: _bars.value, status: _status),
              const SizedBox(height: 14),
              _Scoreboard(controller: _text, yellow: yellow),
              const SizedBox(height: 14),
              _Extremometer(
                value: _intensity,
                onChanged: (v) => setState(() => _intensity = v),
              ),
              const SizedBox(height: 8),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text('ARENA INTRO PACK',
                    style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5)),
                subtitle: Text(_arenaPrefix ? kIntros[_intro] : 'Pure contrast — verbatim only',
                    style: const TextStyle(color: Colors.grey)),
                value: _arenaPrefix,
                activeColor: const Color(0xFFFF1F1F),
                onChanged: (v) => setState(() => _arenaPrefix = v),
              ),
              if (_arenaPrefix)
                Wrap(
                  spacing: 6,
                  runSpacing: -6,
                  children: [
                    for (var i = 0; i < kIntros.length; i++)
                      ChoiceChip(
                        label: Text(kIntros[i], style: const TextStyle(fontSize: 11)),
                        selected: _intro == i,
                        selectedColor: const Color(0xFF8B0000),
                        onSelected: (_) => setState(() => _intro = i),
                      ),
                  ],
                ),
              const SizedBox(height: 8),
              Row(
                children: [
                  const Text('VOICE', style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: DropdownButton<String>(
                      value: _voice,
                      isExpanded: true,
                      items: [
                        for (final e in kVoices.entries)
                          DropdownMenuItem(value: e.key, child: Text('${e.key} — ${e.value}')),
                      ],
                      onChanged: (v) => setState(() => _voice = v ?? 'Algenib'),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 18),
              _CautionButton(loading: _loading, onPressed: _loading ? null : _monsterfy),
              const SizedBox(height: 18),
              _FlameBars(level: _bars.value, active: _playing, rng: _rng),
              const SizedBox(height: 10),
              _CassetteDeck(
                player: _player,
                hasClip: _lastClip != null,
                onShare: _share,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------- widgets

class _ChromeHeader extends StatelessWidget {
  const _ChromeHeader({required this.playing, required this.level, required this.status});
  final bool playing;
  final double level;
  final String status;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(10),
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFFEDEDED), Color(0xFF8A8A8A), Color(0xFFD9D9D9), Color(0xFF5A5A5A)],
          stops: [0, .45, .55, 1],
        ),
        boxShadow: const [BoxShadow(color: Colors.black87, blurRadius: 10, offset: Offset(0, 4))],
      ),
      child: Row(
        children: [
          const Expanded(
            child: Text('TRUCK-A-FY',
                style: TextStyle(
                  fontSize: 30,
                  fontWeight: FontWeight.w900,
                  fontStyle: FontStyle.italic,
                  letterSpacing: 2,
                  color: Color(0xFF1A1A1A),
                  shadows: [Shadow(color: Colors.white, offset: Offset(1, 1))],
                )),
          ),
          _VuMeter(level: playing ? .4 + level * .6 : 0),
        ],
      ),
    ).withStatusLine(status);
  }
}

extension on Widget {
  Widget withStatusLine(String status) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          this,
          const SizedBox(height: 6),
          Text(status,
              textAlign: TextAlign.center,
              style: const TextStyle(
                  fontFamily: 'monospace', fontSize: 12, color: Color(0xFFFF1F1F), letterSpacing: 2)),
        ],
      );
}

class _VuMeter extends StatelessWidget {
  const _VuMeter({required this.level});
  final double level;
  @override
  Widget build(BuildContext context) {
    const n = 10;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < n; i++)
          Container(
            width: 6,
            height: 8 + i * 1.6,
            margin: const EdgeInsets.only(left: 2),
            decoration: BoxDecoration(
              color: i / n < level
                  ? (i < 6 ? Colors.greenAccent : i < 8 ? Colors.yellow : Colors.red)
                  : Colors.black38,
              borderRadius: BorderRadius.circular(1),
            ),
          ),
      ],
    );
  }
}

class _Scoreboard extends StatelessWidget {
  const _Scoreboard({required this.controller, required this.yellow});
  final TextEditingController controller;
  final Color yellow;
  @override
  Widget build(BuildContext context) {
    return TextField(
      controller: controller,
      maxLines: 4,
      minLines: 3,
      maxLength: 600,
      textCapitalization: TextCapitalization.sentences,
      style: TextStyle(color: yellow, fontSize: 18, fontFamily: 'monospace', fontWeight: FontWeight.bold),
      decoration: InputDecoration(
        hintText: 'Type a boring message...\n(e.g. "Pick up oat milk on the way home.")',
        hintStyle: const TextStyle(color: Colors.grey),
        filled: true,
        fillColor: Colors.black,
        counterStyle: const TextStyle(color: Colors.grey),
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFFF1F1F), width: 2),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: const BorderSide(color: Color(0xFFFF1F1F), width: 2),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(10),
          borderSide: BorderSide(color: yellow, width: 3),
        ),
      ),
    );
  }
}

class _Extremometer extends StatelessWidget {
  const _Extremometer({required this.value, required this.onChanged});
  final double value;
  final ValueChanged<double> onChanged;
  String get _label {
    if (value < .25) return 'LOCAL RADIO AD';
    if (value < .5) return 'REGIONAL PROMO';
    if (value < .75) return 'STADIUM SPECTACULAR';
    return '1990s GRAVE DESTRUCTION';
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('EXTREMEMETER',
                style: TextStyle(fontWeight: FontWeight.w900, letterSpacing: 1.5)),
            Text(_label,
                style: const TextStyle(color: Color(0xFFFFD600), fontWeight: FontWeight.bold, fontSize: 12)),
          ],
        ),
        SliderTheme(
          data: SliderTheme.of(context).copyWith(
            activeTrackColor: const Color(0xFFFF1F1F),
            thumbColor: const Color(0xFFFFD600),
            trackHeight: 8,
          ),
          child: Slider(value: value, onChanged: onChanged),
        ),
      ],
    );
  }
}

class _CautionButton extends StatelessWidget {
  const _CautionButton({required this.loading, required this.onPressed});
  final bool loading;
  final VoidCallback? onPressed;
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(color: const Color(0xFFFF1F1F).withOpacity(loading ? .2 : .6), blurRadius: 24, spreadRadius: 2),
          const BoxShadow(color: Colors.black, blurRadius: 0, offset: Offset(0, 6)),
        ],
      ),
      child: CustomPaint(
        painter: _CautionStripes(),
        child: Padding(
          padding: const EdgeInsets.all(6),
          child: ElevatedButton(
            onPressed: onPressed,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFFD10000),
              disabledBackgroundColor: const Color(0xFF6E0000),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 22),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
            ),
            child: loading
                ? const SizedBox(height: 26, width: 26, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 3))
                : const Text('MONSTER-FY MESSAGE!',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, letterSpacing: 1.5)),
          ),
        ),
      ),
    );
  }
}

class _CautionStripes extends CustomPainter {
  @override
  void paint(Canvas canvas, Size size) {
    final r = RRect.fromRectAndRadius(Offset.zero & size, const Radius.circular(14));
    canvas.clipRRect(r);
    canvas.drawRect(Offset.zero & size, Paint()..color = const Color(0xFFFFD600));
    final p = Paint()..color = Colors.black;
    const w = 18.0;
    for (double x = -size.height; x < size.width + size.height; x += w * 2) {
      canvas.drawPath(
        Path()
          ..moveTo(x, 0)
          ..lineTo(x + w, 0)
          ..lineTo(x + w - size.height, size.height)
          ..lineTo(x - size.height, size.height)
          ..close(),
        p,
      );
    }
  }

  @override
  bool shouldRepaint(covariant CustomPainter old) => false;
}

class _FlameBars extends StatelessWidget {
  const _FlameBars({required this.level, required this.active, required this.rng});
  final double level;
  final bool active;
  final Random rng;
  @override
  Widget build(BuildContext context) {
    const n = 28;
    return SizedBox(
      height: 70,
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          for (var i = 0; i < n; i++)
            Builder(builder: (_) {
              final h = active ? 8 + rng.nextDouble() * 62 * (.4 + level * .6) : 4.0;
              return AnimatedContainer(
                duration: const Duration(milliseconds: 90),
                width: 7,
                height: h,
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(2),
                  gradient: const LinearGradient(
                    begin: Alignment.bottomCenter,
                    end: Alignment.topCenter,
                    colors: [Color(0xFFFF1F1F), Color(0xFFFF8A00), Color(0xFFFFD600)],
                  ),
                ),
              );
            }),
        ],
      ),
    );
  }
}

class _CassetteDeck extends StatelessWidget {
  const _CassetteDeck({required this.player, required this.hasClip, required this.onShare});
  final AudioPlayer player;
  final bool hasClip;
  final VoidCallback onShare;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF1E1E1E),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF3A3A3A), width: 2),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceEvenly,
        children: [
          StreamBuilder<PlayerState>(
            stream: player.playerStateStream,
            builder: (context, snap) {
              final playing = snap.data?.playing ?? false;
              final done = snap.data?.processingState == ProcessingState.completed;
              return IconButton.filled(
                iconSize: 34,
                onPressed: !hasClip
                    ? null
                    : () async {
                        if (done) await player.seek(Duration.zero);
                        playing && !done ? player.pause() : player.play();
                      },
                icon: Icon(playing && !done ? Icons.pause : Icons.play_arrow),
              );
            },
          ),
          IconButton.filled(
            iconSize: 34,
            onPressed: hasClip ? () => player.seek(Duration.zero) : null,
            icon: const Icon(Icons.replay),
          ),
          FilledButton.icon(
            onPressed: hasClip ? onShare : null,
            style: FilledButton.styleFrom(backgroundColor: const Color(0xFFFF1F1F)),
            icon: const Icon(Icons.ios_share),
            label: const Text('SHARE', style: TextStyle(fontWeight: FontWeight.w900)),
          ),
        ],
      ),
    );
  }
}
