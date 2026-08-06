import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';
import '../models.dart';

/// Manuel salon editörünün tuvali (şartname M5).
///
/// *"Tuval: boş bir ızgara. Yakınlaştırma ve kaydırma desteklenir, hem parmakla
/// hem fareyle çalışır."*
///
/// *"Masalar serbestçe sürüklenir ama bırakıldığında en yakın ızgara noktasına
/// oturur. Kullanıcı bunu fark etmez, sadece düzen kendiliğinden hizalı
/// çıkar."* Oturma hesabı burada; sunucu hazır hücre koordinatı alıyor ve
/// çakışmayı kendi doğruluyor.
class LayoutCanvas extends StatelessWidget {
  const LayoutCanvas({
    super.key,
    required this.layout,
    required this.controller,
    required this.tool,
    required this.busy,
    required this.onPlace,
    required this.onMoveTable,
    required this.onMoveArea,
    required this.onSelectTable,
    required this.onSelectArea,
    this.selectedTableId,
    this.selectedAreaId,
  });

  final EventLayout layout;
  final TransformationController controller;

  /// Seçili araç; boşsa dokunma yalnızca seçim yapar.
  final CanvasTool? tool;

  /// Kaydetme sürerken sürükleme kapanıyor: yarım kalan istekle çakışmasın.
  final bool busy;

  final void Function(int gridX, int gridY) onPlace;
  final void Function(EventTable table, int gridX, int gridY) onMoveTable;
  final void Function(LayoutArea area, int gridX, int gridY) onMoveArea;
  final ValueChanged<EventTable> onSelectTable;
  final ValueChanged<LayoutArea> onSelectArea;
  final int? selectedTableId;
  final int? selectedAreaId;

  int get _columns => layout.gridWidth ?? 0;
  int get _rows => layout.gridHeight ?? 0;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).colorScheme;

    return InteractiveViewer(
      transformationController: controller,
      // Tuval görüntü alanından büyük olabilir; kısıtlanmazsa ızgara ekrana
      // sıkıştırılır ve hücreler ezilir.
      constrained: false,
      boundaryMargin: const EdgeInsets.all(AppSpacing.xl),
      minScale: minCanvasScale,
      maxScale: maxCanvasScale,
      child: SizedBox(
        width: _columns * AppSpacing.gridCell,
        height: _rows * AppSpacing.gridCell,
        child: Stack(
          children: [
            // Izgara ve boş hücreye dokunma en altta: üstteki masalar dokunmayı
            // kendileri karşılıyor.
            Positioned.fill(
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onTapUp: (details) => _placeAt(details.localPosition),
                child: CustomPaint(
                  painter: _GridPainter(
                    columns: _columns,
                    rows: _rows,
                    lineColor: colors.outlineVariant,
                    surfaceColor: colors.surfaceContainerLowest,
                  ),
                ),
              ),
            ),
            for (final area in layout.areas)
              _CanvasItem(
                key: ValueKey('area-${area.id}'),
                gridX: area.gridX,
                gridY: area.gridY,
                cellsWide: area.width,
                cellsHigh: area.height,
                columns: _columns,
                rows: _rows,
                enabled: !busy,
                onTap: () => onSelectArea(area),
                onDropped: (x, y) => onMoveArea(area, x, y),
                child: _AreaTile(
                  area: area,
                  selected: area.id == selectedAreaId,
                ),
              ),
            for (final table in layout.tables.where((item) => item.isPlaced))
              _CanvasItem(
                key: ValueKey('table-${table.id}'),
                gridX: table.gridX!,
                gridY: table.gridY!,
                cellsWide: 1,
                cellsHigh: 1,
                columns: _columns,
                rows: _rows,
                enabled: !busy,
                onTap: () => onSelectTable(table),
                onDropped: (x, y) => onMoveTable(table, x, y),
                child: _TableTile(
                  table: table,
                  selected: table.id == selectedTableId,
                ),
              ),
          ],
        ),
      ),
    );
  }

  void _placeAt(Offset position) {
    if (busy || tool == null) return;
    final gridX = (position.dx / AppSpacing.gridCell).floor();
    final gridY = (position.dy / AppSpacing.gridCell).floor();
    if (gridX < 0 || gridY < 0 || gridX >= _columns || gridY >= _rows) return;
    onPlace(gridX, gridY);
  }
}

/// Tuvalin yakınlaştırma sınırları.
///
/// Alt sınırda 24×16 ızgaranın tamamı ekrana sığıyor, üst sınırda tek hücre
/// rahat dokunulacak büyüklükte. Editördeki yakınlaştırma düğmeleri de aynı
/// sınırları kullanıyor.
const double minCanvasScale = 0.2;
const double maxCanvasScale = 2.5;

/// Bırakılan öğenin oturacağı ızgara hücresi (şartname M5).
///
/// *"Masalar serbestçe sürüklenir ama bırakıldığında en yakın ızgara noktasına
/// oturur."* Yuvarlama en yakına: hücrenin yarısını geçen sürükleme bir sonraki
/// hücreye geçiyor, geçmeyen yerinde kalıyor.
///
/// `highest` öğenin başlayabileceği son sütun/satır — çok hücreli alan bloğu
/// tuvalin dışına taşmasın diye genişliği çıkarılmış hâli. Sunucu aynı sınırı
/// ayrıca doğruluyor.
int snapToGrid(double pixels, int highest) {
  return (pixels / AppSpacing.gridCell).round().clamp(0, highest < 0 ? 0 : highest);
}

/// Araç çubuğundan seçilen araç (M5).
///
/// *"Araç çubuğundan tip seçilir, tuvale dokunulur, masa oraya konur."*
enum CanvasTool {
  seatedTable('Oturmalı masa', Icons.event_seat_outlined),
  standingTable('Ayaklı masa', Icons.table_bar_outlined),
  area('Alan bloğu', Icons.crop_square_outlined);

  const CanvasTool(this.label, this.icon);

  final String label;
  final IconData icon;
}

/// Izgara çizgileri.
class _GridPainter extends CustomPainter {
  const _GridPainter({
    required this.columns,
    required this.rows,
    required this.lineColor,
    required this.surfaceColor,
  });

  final int columns;
  final int rows;
  final Color lineColor;
  final Color surfaceColor;

  @override
  void paint(Canvas canvas, Size size) {
    canvas.drawRect(Offset.zero & size, Paint()..color = surfaceColor);

    final line = Paint()
      ..color = lineColor
      ..strokeWidth = 1;
    for (var column = 0; column <= columns; column++) {
      final x = column * AppSpacing.gridCell;
      canvas.drawLine(Offset(x, 0), Offset(x, size.height), line);
    }
    for (var row = 0; row <= rows; row++) {
      final y = row * AppSpacing.gridCell;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), line);
    }
  }

  @override
  bool shouldRepaint(_GridPainter old) =>
      old.columns != columns ||
      old.rows != rows ||
      old.lineColor != lineColor ||
      old.surfaceColor != surfaceColor;
}

/// Tuvale konmuş, sürüklenebilen bir öğe.
///
/// Sürükleme boyunca konum yerelde tutuluyor; parmak kalkınca en yakın ızgara
/// noktasına yuvarlanıp yukarı bildiriliyor. Sunucu reddederse öğe eski
/// yerinde kalır — durum yalnızca sunucudan gelen düzenden besleniyor.
class _CanvasItem extends StatefulWidget {
  const _CanvasItem({
    super.key,
    required this.gridX,
    required this.gridY,
    required this.cellsWide,
    required this.cellsHigh,
    required this.columns,
    required this.rows,
    required this.enabled,
    required this.onTap,
    required this.onDropped,
    required this.child,
  });

  final int gridX;
  final int gridY;
  final int cellsWide;
  final int cellsHigh;
  final int columns;
  final int rows;
  final bool enabled;
  final VoidCallback onTap;
  final void Function(int gridX, int gridY) onDropped;
  final Widget child;

  @override
  State<_CanvasItem> createState() => _CanvasItemState();
}

class _CanvasItemState extends State<_CanvasItem> {
  Offset _drag = Offset.zero;
  bool _dragging = false;

  @override
  void didUpdateWidget(_CanvasItem old) {
    super.didUpdateWidget(old);
    // Sunucudan yeni konum geldi: yerel kaydırma sıfırlanmalı, yoksa öğe iki
    // kez taşınmış görünür.
    if (old.gridX != widget.gridX || old.gridY != widget.gridY) {
      _drag = Offset.zero;
    }
  }

  void _end() {
    final droppedX = snapToGrid(
      widget.gridX * AppSpacing.gridCell + _drag.dx,
      widget.columns - widget.cellsWide,
    );
    final droppedY = snapToGrid(
      widget.gridY * AppSpacing.gridCell + _drag.dy,
      widget.rows - widget.cellsHigh,
    );

    setState(() {
      _drag = Offset.zero;
      _dragging = false;
    });

    if (droppedX != widget.gridX || droppedY != widget.gridY) {
      widget.onDropped(droppedX, droppedY);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Positioned(
      left: widget.gridX * AppSpacing.gridCell + _drag.dx,
      top: widget.gridY * AppSpacing.gridCell + _drag.dy,
      width: widget.cellsWide * AppSpacing.gridCell,
      height: widget.cellsHigh * AppSpacing.gridCell,
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: widget.enabled ? widget.onTap : null,
        // Sürükleme tuvalin kaydırmasından önce geliyor: bu tanıyıcı ağaçta
        // daha derinde, dokunma yarışını o kazanıyor.
        onPanStart: widget.enabled ? (_) => setState(() => _dragging = true) : null,
        onPanUpdate:
            widget.enabled ? (details) => setState(() => _drag += details.delta) : null,
        onPanEnd: widget.enabled ? (_) => _end() : null,
        onPanCancel: widget.enabled
            ? () => setState(() {
                  _drag = Offset.zero;
                  _dragging = false;
                })
            : null,
        child: MouseRegion(
          cursor: widget.enabled ? SystemMouseCursors.grab : MouseCursor.defer,
          child: AnimatedScale(
            scale: _dragging ? 1.06 : 1,
            duration: const Duration(milliseconds: 120),
            child: widget.child,
          ),
        ),
      ),
    );
  }
}

/// Tuvaldeki bir masa: numara büyük, kapasite küçük.
///
/// *"Bu kritik — katılımcı masasını numarayla buluyor."*
class _TableTile extends StatelessWidget {
  const _TableTile({required this.table, required this.selected});

  final EventTable table;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;
    final seated = table.kind == TableKind.seated;

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xs),
      child: Container(
        decoration: BoxDecoration(
          color: selected ? colors.primary : colors.primaryContainer,
          // Oturmalı masa yuvarlak, ayaklı masa köşeli: tip tek bakışta ayırt
          // edilsin.
          shape: seated ? BoxShape.circle : BoxShape.rectangle,
          borderRadius: seated ? null : BorderRadius.circular(AppSpacing.sm),
          border: Border.all(
            color: selected ? colors.primary : colors.outlineVariant,
            width: selected ? 2 : 1,
          ),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              '${table.number}',
              style: theme.textTheme.titleMedium?.copyWith(
                color: selected ? colors.onPrimary : colors.onPrimaryContainer,
              ),
            ),
            Text(
              '${table.capacity}',
              style: theme.textTheme.labelSmall?.copyWith(
                color: selected ? colors.onPrimary : colors.onPrimaryContainer,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Tuvaldeki bir alan bloğu — sahne, giriş, büfe.
class _AreaTile extends StatelessWidget {
  const _AreaTile({required this.area, required this.selected});

  final LayoutArea area;
  final bool selected;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = theme.colorScheme;

    return Padding(
      padding: const EdgeInsets.all(AppSpacing.xs / 2),
      child: Container(
        decoration: BoxDecoration(
          color: colors.tertiaryContainer,
          borderRadius: BorderRadius.circular(AppSpacing.xs),
          border: Border.all(
            color: selected ? colors.tertiary : colors.outlineVariant,
            width: selected ? 2 : 1,
          ),
        ),
        alignment: Alignment.center,
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.xs),
          child: Text(
            area.label,
            textAlign: TextAlign.center,
            overflow: TextOverflow.ellipsis,
            maxLines: 2,
            style: theme.textTheme.labelMedium?.copyWith(
              color: colors.onTertiaryContainer,
            ),
          ),
        ),
      ),
    );
  }
}
