import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../core/widgets/state_views.dart';
import '../event_controller.dart';
import '../models.dart';
import '../wizard/event_wizard_screen.dart';
import 'layout_canvas.dart';
import 'layout_sheets.dart';

/// Manuel salon editörü (şartname M5).
///
/// *"Organizatör salonu ekranda kurar."* Tuval, araç çubuğu, masa paneli ve
/// alan blokları burada; ızgara kuralları sunucuda.
///
/// *"Kaydetme: düzen otomatik kaydedilir."* Her değişiklik anında sunucuya
/// gidiyor — sürükleme sırasında değil, bırakıldığında. Ekranda tutulan düzen
/// hep sunucunun döndürdüğü hâl: reddedilen bir hamle geri alınmış olmuyor,
/// hiç uygulanmamış oluyor.
class LayoutEditorScreen extends ConsumerStatefulWidget {
  const LayoutEditorScreen({super.key, required this.eventId});

  static const routeName = 'layoutEditor';
  static const routePath = '/etkinlikler/:eventId/salon';

  final int eventId;

  @override
  ConsumerState<LayoutEditorScreen> createState() => _LayoutEditorScreenState();
}

class _LayoutEditorScreenState extends ConsumerState<LayoutEditorScreen> {
  final _transformation = TransformationController();

  /// Üzerinde çalışılan düzen — her yanıtla yenileniyor.
  EventLayout? _working;

  CanvasTool? _tool;
  bool _busy = false;
  int? _selectedTableId;
  int? _selectedAreaId;

  @override
  void dispose() {
    _transformation.dispose();
    super.dispose();
  }

  // --- Sunucuya yazma --------------------------------------------------------

  /// Bir değişikliği uygular ve dönen düzeni ekrana alır.
  ///
  /// Hata **mesaj olarak** dönüyor: çağıran onu panelde satır içi gösteriyor ya
  /// da tuvalde şerit olarak. Fırlatılsaydı ekran hata görünümüne düşer,
  /// organizatörün kurduğu düzen gözden kaybolurdu.
  Future<String?> _apply(Future<EventLayout> Function() change) async {
    setState(() => _busy = true);
    try {
      final layout = await change();
      if (mounted) setState(() => _working = layout);
      return null;
    } on ApiException catch (error) {
      return error.message;
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  /// Tuvalde yapılan bir hamle; reddedilirse şeritle bildiriliyor.
  Future<void> _applyOnCanvas(Future<EventLayout> Function() change) async {
    final error = await _apply(change);
    if (error != null) _report(error);
  }

  void _report(String message) {
    if (!mounted) return;
    ScaffoldMessenger.of(context)
      ..clearSnackBars()
      ..showSnackBar(SnackBar(content: Text(message)));
  }

  // --- Tuval hareketleri -----------------------------------------------------

  Future<void> _place(int gridX, int gridY) async {
    final tool = _tool;
    if (tool == null) return;
    final repository = ref.read(eventRepositoryProvider);

    if (tool == CanvasTool.area) {
      final label = await askAreaLabel(context);
      if (label == null || !mounted) return;
      await _applyOnCanvas(() => repository.createArea(
            eventId: widget.eventId,
            label: label,
            gridX: gridX,
            gridY: gridY,
            width: 1,
            height: 1,
          ));
      return;
    }

    final seated = tool == CanvasTool.seatedTable;
    await _applyOnCanvas(() => repository.createTable(
          eventId: widget.eventId,
          kind: seated ? TableKind.seated : TableKind.standing,
          gridX: gridX,
          gridY: gridY,
          seatCount: seated ? _defaultSeatCount : null,
          minPeople: seated ? null : _defaultMinPeople,
          maxPeople: seated ? null : _defaultMaxPeople,
        ));
  }

  Future<void> _moveTable(EventTable table, int gridX, int gridY) {
    return _applyOnCanvas(() => ref.read(eventRepositoryProvider).updateTable(
          eventId: widget.eventId,
          tableId: table.id,
          changes: {'grid_x': gridX, 'grid_y': gridY},
        ));
  }

  Future<void> _moveArea(LayoutArea area, int gridX, int gridY) {
    return _applyOnCanvas(() => ref.read(eventRepositoryProvider).updateArea(
          eventId: widget.eventId,
          areaId: area.id,
          changes: {'grid_x': gridX, 'grid_y': gridY},
        ));
  }

  // --- Paneller --------------------------------------------------------------

  Future<void> _openTable(EventTable table) async {
    setState(() => _selectedTableId = table.id);
    final repository = ref.read(eventRepositoryProvider);

    await showTableSheet(
      context: context,
      table: table,
      onSave: (changes) => _apply(() => repository.updateTable(
            eventId: widget.eventId,
            tableId: table.id,
            changes: changes,
          )),
      onDelete: () => _apply(() => repository.deleteTable(
            eventId: widget.eventId,
            tableId: table.id,
          )),
    );

    if (mounted) setState(() => _selectedTableId = null);
  }

  Future<void> _openArea(LayoutArea area) async {
    setState(() => _selectedAreaId = area.id);
    final repository = ref.read(eventRepositoryProvider);

    await showAreaSheet(
      context: context,
      area: area,
      onSave: (changes) => _apply(() => repository.updateArea(
            eventId: widget.eventId,
            areaId: area.id,
            changes: changes,
          )),
      onDelete: () => _apply(() => repository.deleteArea(
            eventId: widget.eventId,
            areaId: area.id,
          )),
    );

    if (mounted) setState(() => _selectedAreaId = null);
  }

  Future<void> _resizeGrid(EventLayout layout) async {
    final size = await showGridSizeDialog(
      context: context,
      width: layout.gridWidth ?? 0,
      height: layout.gridHeight ?? 0,
    );
    if (size == null || !mounted) return;

    await _applyOnCanvas(
      () => ref.read(eventRepositoryProvider).buildManualLayout(
            eventId: widget.eventId,
            gridWidth: size.$1,
            gridHeight: size.$2,
          ),
    );
  }

  // --- Görünüm ---------------------------------------------------------------

  /// Düğmeyle yakınlaştırma — fare kullanan için (M5).
  ///
  /// Parmakla sıkıştırma ve fare tekerleği `InteractiveViewer`'da zaten var;
  /// düğmeler ikisinin de olmadığı durumu kapatıyor.
  void _zoom(double factor) {
    final scale = _transformation.value.getMaxScaleOnAxis() * factor;
    if (scale < minCanvasScale || scale > maxCanvasScale) return;
    _transformation.value = _transformation.value.clone()
      ..scaleByDouble(factor, factor, 1, 1);
  }

  /// Editörden çıkarken etkinliği tazeler.
  ///
  /// Masa sayısı değiştiyse kapasite özeti ve "kayıtlar açılabilir mi" bilgisi
  /// de değişti; sihirbaz onları etkinlik yanıtından okuyor.
  Future<void> _leave() async {
    await ref.read(eventActionsProvider(widget.eventId)).refreshLayout();
    if (mounted) {
      context.goNamed(
        EventWizardScreen.routeName,
        pathParameters: {'eventId': '${widget.eventId}'},
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final incoming = ref.watch(eventLayoutProvider(widget.eventId));
    final layout = _working ?? incoming.asData?.value;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Salon düzeni'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          tooltip: 'Etkinliğe dön',
          onPressed: _leave,
        ),
        actions: [
          if (layout != null) ...[
            IconButton(
              icon: const Icon(Icons.grid_on_outlined),
              tooltip: 'Izgara boyutu',
              onPressed: _busy ? null : () => _resizeGrid(layout),
            ),
            IconButton(
              icon: const Icon(Icons.zoom_out),
              tooltip: 'Uzaklaştır',
              onPressed: () => _zoom(1 / 1.25),
            ),
            IconButton(
              icon: const Icon(Icons.zoom_in),
              tooltip: 'Yakınlaştır',
              onPressed: () => _zoom(1.25),
            ),
            IconButton(
              icon: const Icon(Icons.center_focus_strong_outlined),
              tooltip: 'Görünümü sıfırla',
              onPressed: () => _transformation.value = Matrix4.identity(),
            ),
          ],
        ],
        bottom: _busy
            ? const PreferredSize(
                preferredSize: Size.fromHeight(2),
                child: LinearProgressIndicator(minHeight: 2),
              )
            : null,
      ),
      body: switch ((layout, incoming)) {
        (null, AsyncLoading()) => const LoadingView(message: 'Salon yükleniyor'),
        (null, AsyncError(:final error)) => ErrorView(
            message: error is ApiException
                ? error.message
                : 'Salon düzeni yüklenemedi.',
            onRetry: () => ref.invalidate(eventLayoutProvider(widget.eventId)),
          ),
        (null, _) => const ErrorView(
            message: 'Bu etkinlikte henüz salon düzeni yok. '
                'Sihirbazın salon adımından manuel düzeni kur.',
          ),
        (final EventLayout value, _) when value.mode != LayoutMode.manual =>
          const ErrorView(
            message: 'Bu etkinlik otomatik salon düzeni kullanıyor. '
                'Kroki için sihirbazın salon adımından manuel moda geç.',
          ),
        (final EventLayout value, _) => _buildEditor(value),
      },
      bottomNavigationBar: layout == null || layout.mode != LayoutMode.manual
          ? null
          : _Toolbar(
              tool: _tool,
              enabled: !_busy,
              onToolChanged: (tool) => setState(() => _tool = tool),
              summary: '${layout.tables.length} masa · '
                  '${layout.seatingCapacity} kişilik · '
                  '${layout.gridWidth}×${layout.gridHeight} ızgara',
            ),
    );
  }

  Widget _buildEditor(EventLayout layout) {
    return Stack(
      children: [
        Positioned.fill(
          child: LayoutCanvas(
            layout: layout,
            controller: _transformation,
            tool: _tool,
            busy: _busy,
            onPlace: _place,
            onMoveTable: _moveTable,
            onMoveArea: _moveArea,
            onSelectTable: _openTable,
            onSelectArea: _openArea,
            selectedTableId: _selectedTableId,
            selectedAreaId: _selectedAreaId,
          ),
        ),
        // Boş durum: ızgara görünür kalıyor, ipucu dokunmayı engellemiyor —
        // organizatörün ilk hamlesi zaten tuvale dokunmak.
        if (layout.isEmpty)
          Positioned.fill(
            child: IgnorePointer(
              child: EmptyView(
                icon: Icons.grid_view_outlined,
                message: _tool == null
                    ? 'Salon boş. Aşağıdan bir araç seç, sonra tuvale dokun.'
                    : '${_tool!.label} seçili. Koymak istediğin hücreye dokun.',
              ),
            ),
          ),
      ],
    );
  }
}

const int _defaultSeatCount = 6;
const int _defaultMinPeople = 3;
const int _defaultMaxPeople = 8;

/// Araç çubuğu (M5).
///
/// *"Araç çubuğundan tip seçilir, tuvale dokunulur, masa oraya konur."*
/// Araç seçili değilken dokunma yalnızca seçim yapıyor; yanlışlıkla masa
/// serpiştirmeyi engelliyor.
class _Toolbar extends StatelessWidget {
  const _Toolbar({
    required this.tool,
    required this.enabled,
    required this.onToolChanged,
    required this.summary,
  });

  final CanvasTool? tool;
  final bool enabled;
  final ValueChanged<CanvasTool?> onToolChanged;
  final String summary;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.md,
          AppSpacing.sm,
          AppSpacing.md,
          AppSpacing.sm,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  for (final option in CanvasTool.values) ...[
                    ChoiceChip(
                      avatar: Icon(option.icon, size: AppSpacing.md),
                      label: Text(option.label),
                      selected: tool == option,
                      onSelected: enabled
                          ? (chosen) => onToolChanged(chosen ? option : null)
                          : null,
                    ),
                    const SizedBox(width: AppSpacing.sm),
                  ],
                ],
              ),
            ),
            const SizedBox(height: AppSpacing.xs),
            Text(
              summary,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Izgara boyutu penceresi.
///
/// *"Boyutu ayarlanabilir (kaça kaç hücre)."* Küçültme dışarıda öğe
/// bırakacaksa sunucu reddediyor ve hangi masaların taşınması gerektiğini
/// söylüyor.
Future<(int, int)?> showGridSizeDialog({
  required BuildContext context,
  required int width,
  required int height,
}) {
  return showDialog<(int, int)>(
    context: context,
    builder: (context) => _GridSizeDialog(width: width, height: height),
  );
}

class _GridSizeDialog extends StatefulWidget {
  const _GridSizeDialog({required this.width, required this.height});

  final int width;
  final int height;

  @override
  State<_GridSizeDialog> createState() => _GridSizeDialogState();
}

class _GridSizeDialogState extends State<_GridSizeDialog> {
  late int _width = widget.width;
  late int _height = widget.height;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Izgara boyutu'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _DialogStepper(
            label: 'Genişlik',
            value: _width,
            onChanged: (value) => setState(() => _width = value),
          ),
          _DialogStepper(
            label: 'Yükseklik',
            value: _height,
            onChanged: (value) => setState(() => _height = value),
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Vazgeç'),
        ),
        FilledButton(
          onPressed: () => Navigator.of(context).pop((_width, _height)),
          child: const Text('Uygula'),
        ),
      ],
    );
  }
}

class _DialogStepper extends StatelessWidget {
  const _DialogStepper({
    required this.label,
    required this.value,
    required this.onChanged,
  });

  // Sunucudaki sınırlarla aynı: 2 ile 60 hücre arası.
  static const int _lowest = 2;
  static const int _highest = 60;

  final String label;
  final int value;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(child: Text(label, style: Theme.of(context).textTheme.bodyLarge)),
        IconButton.outlined(
          onPressed: value > _lowest ? () => onChanged(value - 1) : null,
          icon: const Icon(Icons.remove),
          tooltip: '$label azalt',
        ),
        SizedBox(
          width: 56,
          child: Text(
            '$value',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
        ),
        IconButton.outlined(
          onPressed: value < _highest ? () => onChanged(value + 1) : null,
          icon: const Icon(Icons.add),
          tooltip: '$label artır',
        ),
      ],
    );
  }
}
