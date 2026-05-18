import React, { useEffect, useMemo, useState } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Select from '@mui/material/Select';
import MenuItem from '@mui/material/MenuItem';
import Tooltip from '@mui/material/Tooltip';
import RefreshRoundedIcon from '@mui/icons-material/RefreshRounded';
import CloseRoundedIcon from '@mui/icons-material/CloseRounded';
import PlayArrowRoundedIcon from '@mui/icons-material/PlayArrowRounded';
import ContentCopyRoundedIcon from '@mui/icons-material/ContentCopyRounded';
import ArticleOutlinedIcon from '@mui/icons-material/ArticleOutlined';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import {
  fetchPlans,
  fetchPlanDetail,
  executePlan,
  selectPlan,
  PersistentPlanSummary,
} from '@/shared/state/plansSlice';
import { fetchSessions } from '@/shared/state/agentsSlice';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';

interface Props {
  onClose: () => void;
  collapsed?: boolean;
  dashboardId?: string;
  onGoToAgent?: (sessionId: string) => void;
}

function formatDate(value?: string): string {
  if (!value) return 'Sin fecha';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

function statusTone(status?: string): { label: string; bg: string; color: string } {
  const normalized = String(status || 'draft').toLowerCase();
  if (normalized === 'completed') return { label: 'completed', bg: 'rgba(16, 185, 129, 0.12)', color: '#047857' };
  if (normalized === 'running') return { label: 'running', bg: 'rgba(59, 130, 246, 0.12)', color: '#1d4ed8' };
  if (normalized === 'error') return { label: 'error', bg: 'rgba(239, 68, 68, 0.12)', color: '#b91c1c' };
  return { label: normalized, bg: 'rgba(107, 114, 128, 0.12)', color: '#4b5563' };
}

const PersistentPlansCard: React.FC<Props> = ({ onClose, collapsed = false, dashboardId, onGoToAgent }) => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();

  const plans = useAppSelector((s) => s.plans.items);
  const loading = useAppSelector((s) => s.plans.loading);
  const detailLoading = useAppSelector((s) => s.plans.detailLoading);
  const executing = useAppSelector((s) => s.plans.executing);
  const error = useAppSelector((s) => s.plans.error);
  const selectedPlanId = useAppSelector((s) => s.plans.selectedPlanId);
  const selectedPlanDetail = useAppSelector((s) => s.plans.selectedPlanDetail);
  const sessions = useAppSelector((s) => s.agents.sessions);

  const [selectedSessionId, setSelectedSessionId] = useState('');

  const planList = useMemo(() => {
    return Object.values(plans).sort((a, b) => {
      const at = new Date(a.updated_at || a.created_at || 0).getTime();
      const bt = new Date(b.updated_at || b.created_at || 0).getTime();
      return bt - at;
    });
  }, [plans]);

  const agentSessions = useMemo(() => {
    return Object.values(sessions).filter((s) => {
      if (s.mode !== 'agent') return false;
      if (dashboardId && s.dashboard_id !== dashboardId) return false;
      return true;
    });
  }, [sessions, dashboardId]);

  useEffect(() => {
    dispatch(fetchPlans({ dashboardId }));
    dispatch(fetchSessions({ dashboardId }));
  }, [dispatch, dashboardId]);

  useEffect(() => {
    if (selectedSessionId && agentSessions.some((session) => session.id === selectedSessionId)) return;

    const firstAgent = agentSessions[0];
    setSelectedSessionId(firstAgent ? firstAgent.id : '');
  }, [agentSessions, selectedSessionId]);

  const selectedPlan = selectedPlanId ? plans[selectedPlanId] : null;
  const detailPlan = selectedPlanDetail?.plan;
  const selectedDisplayTitle =
    detailPlan?.title ||
    selectedPlan?.title ||
    selectedPlan?.display_label ||
    'Plan sin seleccionar';

  const selectedPlanStatus = String(detailPlan?.status || selectedPlan?.status || 'draft').toLowerCase();
  const executeButtonLabel =
    executing || selectedPlanStatus === 'running'
      ? 'Ejecutando plan'
      : selectedPlanStatus === 'completed'
        ? 'Ejecutar nuevamente'
        : selectedPlanStatus === 'error'
          ? 'Reintentar ejecución'
          : 'Ejecutar plan';

  const handleRefresh = () => {
    dispatch(fetchPlans({ dashboardId }));
    dispatch(fetchSessions({ dashboardId }));
    if (selectedPlanId) dispatch(fetchPlanDetail(selectedPlanId));
  };

  const handleSelectPlan = (plan: PersistentPlanSummary) => {
    dispatch(selectPlan(plan.id));
    dispatch(fetchPlanDetail(plan.id));
  };

  const handleCopyPlanId = async (planId: string) => {
    try {
      await navigator.clipboard.writeText(planId);
    } catch {
      // Copiar ID no debe romper la card.
    }
  };

  const handleExecute = async () => {
    if (!selectedPlanId || !selectedSessionId) return;

    const planIdToRefresh = selectedPlanId;
    await dispatch(executePlan({ planId: planIdToRefresh, sessionId: selectedSessionId }));

    const pollDelays = [500, 1500, 3000, 5000, 8000, 12000, 16000, 22000, 30000];

    pollDelays.forEach((delay) => {
      window.setTimeout(async () => {
        dispatch(fetchPlans({ dashboardId }));
        dispatch(fetchPlanDetail(planIdToRefresh));
      }, delay);
    });
  };

  return (
    <Box
      sx={{
        width: '100%',
        height: '100%',
        bgcolor: c.bg.surface,
        color: c.text.primary,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        borderRadius: 1,
      }}
    >
      <Box
        className="drag-handle"
        sx={{
          px: 2,
          py: 1.35,
          borderBottom: `1px solid ${c.border.default}`,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          cursor: 'grab',
          '&:active': { cursor: 'grabbing' },
        }}
      >
        <ArticleOutlinedIcon sx={{ fontSize: 19, color: c.text.secondary, flexShrink: 0 }} />
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography sx={{ fontSize: '0.95rem', fontWeight: 700, lineHeight: 1.2 }}>
            Planes persistentes
          </Typography>
          <Typography sx={{ fontSize: '0.75rem', color: c.text.secondary }}>
            Ejecutá planes guardados en sesiones Agent
          </Typography>
        </Box>
        <Tooltip title="Refrescar">
          <IconButton size="small" onClick={handleRefresh}>
            <RefreshRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
        <Tooltip title="Cerrar">
          <IconButton size="small" onClick={onClose}>
            <CloseRoundedIcon sx={{ fontSize: 18 }} />
          </IconButton>
        </Tooltip>
      </Box>

      {!collapsed && error && (
        <Box sx={{ px: 2, py: 1, bgcolor: 'rgba(239, 68, 68, 0.08)', color: '#b91c1c' }}>
          <Typography sx={{ fontSize: '0.78rem' }}>{error}</Typography>
        </Box>
      )}

      {!collapsed && (
      <Box sx={{ display: 'flex', minHeight: 0, flex: 1 }}>
        <Box
          sx={{
            width: 240,
            height: '100%',
            overflowY: 'auto',
            borderRight: `1px solid ${c.border.default}`,
            p: 1,
          }}
        >
          {loading && (
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, p: 1 }}>
              <CircularProgress size={14} />
              <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary }}>
                Cargando planes
              </Typography>
            </Box>
          )}

          {!loading && planList.length === 0 && (
            <Typography sx={{ fontSize: '0.8rem', color: c.text.secondary, p: 1 }}>
              No hay planes persistentes.
            </Typography>
          )}

          {planList.map((plan) => {
            const tone = statusTone(plan.status);
            const active = selectedPlanId === plan.id;
            return (
              <Box
                key={plan.id}
                onClick={() => handleSelectPlan(plan)}
                sx={{
                  p: 1,
                  mb: 0.75,
                  borderRadius: 1,
                  cursor: 'pointer',
                  bgcolor: active ? c.bg.subtle : 'transparent',
                  border: `1px solid ${active ? c.border.default : 'transparent'}`,
                  '&:hover': { bgcolor: c.bg.subtle },
                }}
              >
                <Typography
                  sx={{
                    fontSize: '0.8rem',
                    fontWeight: 650,
                    lineHeight: 1.25,
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                    overflow: 'hidden',
                  }}
                >
                  {plan.display_label || `Plan · ${plan.title}`}
                </Typography>
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75, mt: 0.75 }}>
                  <Chip
                    label={tone.label}
                    size="small"
                    sx={{
                      height: 20,
                      fontSize: '0.68rem',
                      bgcolor: tone.bg,
                      color: tone.color,
                      fontWeight: 650,
                      borderRadius: 1,
                    }}
                  />
                </Box>
                <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, mt: 0.65 }}>
                  {formatDate(plan.updated_at || plan.created_at)}
                </Typography>
              </Box>
            );
          })}
        </Box>

        <Box sx={{ flex: 1, minWidth: 0, p: 1.5, height: '100%', overflowY: 'auto' }}>
          {!selectedPlanId && (
            <Typography sx={{ fontSize: '0.82rem', color: c.text.secondary }}>
              Seleccioná un plan para ver detalles.
            </Typography>
          )}

          {selectedPlanId && (
            <>
              <Box sx={{ display: 'flex', alignItems: 'flex-start', gap: 1 }}>
                <Box sx={{ flex: 1, minWidth: 0 }}>
                  <Typography sx={{ fontSize: '0.95rem', fontWeight: 750, lineHeight: 1.25 }}>
                    Plan · {selectedDisplayTitle}
                  </Typography>
                  <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, mt: 0.6, wordBreak: 'break-all' }}>
                    {selectedPlanId}
                  </Typography>
                </Box>
                <Tooltip title="Copiar plan_id">
                  <IconButton size="small" onClick={() => handleCopyPlanId(selectedPlanId)}>
                    <ContentCopyRoundedIcon sx={{ fontSize: 16 }} />
                  </IconButton>
                </Tooltip>
              </Box>

              {detailLoading && (
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mt: 2 }}>
                  <CircularProgress size={14} />
                  <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary }}>
                    Cargando detalle
                  </Typography>
                </Box>
              )}

              {detailPlan && (
                <Box sx={{ mt: 1.5 }}>
                  <Chip
                    label={detailPlan.status || selectedPlan?.status || 'draft'}
                    size="small"
                    sx={{
                      height: 22,
                      fontSize: '0.7rem',
                      fontWeight: 650,
                      borderRadius: 1,
                      bgcolor: statusTone(detailPlan.status || selectedPlan?.status).bg,
                      color: statusTone(detailPlan.status || selectedPlan?.status).color,
                    }}
                  />

                  <Box sx={{ mt: 1.5 }}>
                    <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, fontWeight: 700, mb: 0.5 }}>
                      Contenido
                    </Typography>
                    <Box
                      sx={{
                        p: 1,
                        bgcolor: c.bg.subtle,
                        border: `1px solid ${c.border.default}`,
                        borderRadius: 1,
                      }}
                    >
                      <Typography sx={{ fontSize: '0.78rem', whiteSpace: 'pre-wrap', lineHeight: 1.45 }}>
                        {detailPlan.content || 'Sin contenido.'}
                      </Typography>
                    </Box>
                  </Box>

                  <Box sx={{ mt: 1.5 }}>
                    <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, fontWeight: 700, mb: 0.75 }}>
                      Elegí Agent ejecutor
                    </Typography>
                    <Select
                      size="small"
                      value={selectedSessionId}
                      onChange={(e) => setSelectedSessionId(String(e.target.value))}
                      fullWidth
                      displayEmpty
                      sx={{
                        fontSize: '0.78rem',
                        borderRadius: 1,
                        mb: 1,
                      }}
                    >
                      {agentSessions.length === 0 && (
                        <MenuItem value="" disabled>
                          No hay sesiones Agent
                        </MenuItem>
                      )}
                      {agentSessions.map((session) => (
                        <MenuItem key={session.id} value={session.id}>
                          {session.display_label || `Agent · ${session.name}`}
                        </MenuItem>
                      ))}
                    </Select>
                    <Typography sx={{ fontSize: '0.7rem', color: c.text.ghost, mb: 1 }}>
                      Este Agent recibirá el contenido real del plan persistente cuando presiones Ejecutar plan.
                    </Typography>
                    <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap' }}>
                      <Button
                        variant="contained"
                        size="small"
                        startIcon={executing ? <CircularProgress size={14} color="inherit" /> : <PlayArrowRoundedIcon />}
                        disabled={!selectedPlanId || !selectedSessionId || executing || selectedPlanStatus === 'running'}
                        onClick={handleExecute}
                        sx={{ borderRadius: 1, textTransform: 'none', fontWeight: 700 }}
                      >
                        {executeButtonLabel}
                      </Button>
                      {detailPlan.last_execution_session_id && detailPlan.last_execution_session_id !== selectedSessionId && (
                        <Button
                          variant="outlined"
                          size="small"
                          onClick={() => detailPlan.last_execution_session_id && onGoToAgent?.(detailPlan.last_execution_session_id)}
                          sx={{ borderRadius: 1, textTransform: 'none', fontWeight: 700 }}
                        >
                          Ver último Agent ejecutor
                        </Button>
                      )}
                    </Box>
                  </Box>

                  <Box sx={{ mt: 1.5 }}>
                    <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, fontWeight: 700 }}>
                      Estado
                    </Typography>
                    <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary, mt: 0.5 }}>
                      Fase actual: {detailPlan.current_phase_index ?? 0}
                    </Typography>
                    <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary }}>
                      Completadas: {(detailPlan.completed_phase_indexes || []).join(', ') || 'ninguna'}
                    </Typography>
                    <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary }}>
                      Fallidas: {(detailPlan.failed_phase_indexes || []).join(', ') || 'ninguna'}
                    </Typography>
                    <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary }}>
                      Agent ejecutor: {detailPlan.last_execution_session_id || 'ninguno'}
                    </Typography>
                    <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary }}>
                      Actualizado: {formatDate(detailPlan.updated_at)}
                    </Typography>
                    {detailPlan.last_error && (
                      <Box sx={{ mt: 0.75, p: 1, borderRadius: 1, bgcolor: 'rgba(239, 68, 68, 0.08)', color: '#b91c1c' }}>
                        <Typography sx={{ fontSize: '0.76rem', whiteSpace: 'pre-wrap' }}>
                          {detailPlan.last_error}
                        </Typography>
                      </Box>
                    )}
                  </Box>

                  <Box sx={{ mt: 1.5 }}>
                    <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, fontWeight: 700, mb: 0.75 }}>
                      Fases
                    </Typography>
                    {(!detailPlan.phases || detailPlan.phases.length === 0) && (
                      <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary }}>
                        Este plan no tiene fases estructuradas.
                      </Typography>
                    )}
                    {(detailPlan.phases || []).map((phase, index) => {
                      const completed = (detailPlan.completed_phase_indexes || []).includes(index);
                      const failed = (detailPlan.failed_phase_indexes || []).includes(index);
                      const current = (detailPlan.current_phase_index ?? 0) === index;
                      const phaseStatus = failed ? 'failed' : completed ? 'completed' : current ? 'current' : (phase.status || 'pending');
                      const tone = statusTone(phaseStatus === 'current' ? 'running' : phaseStatus);
                      const title = phase.title || phase.name || `Fase ${index + 1}`;
                      const description = phase.description || phase.content || '';

                      return (
                        <Box
                          key={`${title}-${index}`}
                          sx={{
                            p: 1,
                            mb: 0.75,
                            borderRadius: 1,
                            border: `1px solid ${current ? c.accent.primary : c.border.default}`,
                            bgcolor: current ? c.bg.subtle : 'transparent',
                          }}
                        >
                          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.75 }}>
                            <Typography sx={{ fontSize: '0.78rem', fontWeight: 700, flex: 1, minWidth: 0 }}>
                              {index}. {title}
                            </Typography>
                            <Chip
                              label={phaseStatus}
                              size="small"
                              sx={{
                                height: 20,
                                fontSize: '0.66rem',
                                bgcolor: tone.bg,
                                color: tone.color,
                                fontWeight: 650,
                                borderRadius: 1,
                              }}
                            />
                          </Box>
                          {description && (
                            <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, mt: 0.5, whiteSpace: 'pre-wrap' }}>
                              {description}
                            </Typography>
                          )}
                        </Box>
                      );
                    })}
                  </Box>
                </Box>
              )}
            </>
          )}
        </Box>
      </Box>
      )}
    </Box>
  );
};

export default PersistentPlansCard;
