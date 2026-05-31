import React, { useEffect, useState, useMemo, useCallback } from 'react';
import Box from '@mui/material/Box';
import Typography from '@mui/material/Typography';
import Button from '@mui/material/Button';
import Dialog from '@mui/material/Dialog';
import DialogTitle from '@mui/material/DialogTitle';
import DialogContent from '@mui/material/DialogContent';
import DialogActions from '@mui/material/DialogActions';
import TextField from '@mui/material/TextField';
import IconButton from '@mui/material/IconButton';
import Chip from '@mui/material/Chip';
import CircularProgress from '@mui/material/CircularProgress';
import Tooltip from '@mui/material/Tooltip';
import Collapse from '@mui/material/Collapse';
import Snackbar from '@mui/material/Snackbar';
import Alert from '@mui/material/Alert';
import InputAdornment from '@mui/material/InputAdornment';
import ToggleButton from '@mui/material/ToggleButton';
import ToggleButtonGroup from '@mui/material/ToggleButtonGroup';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';
import TerminalIcon from '@mui/icons-material/Terminal';
import DescriptionIcon from '@mui/icons-material/Description';
import SearchIcon from '@mui/icons-material/Search';
import DownloadIcon from '@mui/icons-material/Download';
import OpenInNewIcon from '@mui/icons-material/OpenInNew';
import KeyboardArrowDownIcon from '@mui/icons-material/KeyboardArrowDown';
import KeyboardArrowRightIcon from '@mui/icons-material/KeyboardArrowRight';
import FolderIcon from '@mui/icons-material/Folder';
import MoreHorizIcon from '@mui/icons-material/MoreHoriz';
import CodeIcon from '@mui/icons-material/Code';
import VisibilityIcon from '@mui/icons-material/Visibility';
import AutoFixHighIcon from '@mui/icons-material/AutoFixHigh';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { useClaudeTokens } from '@/shared/styles/ThemeContext';
import { useAppDispatch, useAppSelector } from '@/shared/hooks';
import {
  fetchSkills,
  fetchSkillCandidates,
  fetchSkillCandidateRequirementsContract,
  fetchSkillCandidateQualityReview,
  fetchSkillCandidateResearchContract,
  fetchSkillCandidateHarnessFull,
  approveSkillCandidateResearch,
  fetchSkillCandidateImprovementProposal,
  applySkillCandidateImprovementProposal,
  previewSkillImport,
  createSkillCandidateFromImport,
  createSkillCandidate,
  createSkill,
  updateSkill,
  deleteSkill,
  approveSkillCandidate,
  installSkillCandidate,
  rejectSkillCandidate,
  deleteSkillCandidate,
  Skill,
  SkillCandidateRequirementsContract,
  SkillCandidateQualityReview,
  SkillCandidateResearchContract,
  SkillCandidateImprovementProposal,
  SkillHarnessFullReport,
  SkillSpecCandidate,
} from '@/shared/state/skillsSlice';
import {
  fetchAllRegistrySkills,
  fetchSkillRegistryStats,
  fetchSkillDetail,
  RegistrySkill,
  RegistrySkillDetail,
} from '@/shared/state/skillRegistrySlice';
import SkillBuilderChat, { SkillPreviewData } from './SkillBuilderChat';

interface SkillForm {
  name: string;
  description: string;
  content: string;
  command: string;
}

type Selection =
  | { type: 'registry'; name: string }
  | { type: 'local'; id: string }
  | { type: 'candidate'; id: string }
  | { type: 'builder-preview' }
  | null;

const emptyForm: SkillForm = { name: '', description: '', content: '', command: '' };

const SIDEBAR_W = 260;

const Skills: React.FC = () => {
  const c = useClaudeTokens();
  const dispatch = useAppDispatch();
  const {
    items,
    loading,
    candidates,
    candidateRequirementsContracts,
    candidateRequirementsContractsLoading,
    candidateRequirementsContractsError,
    candidateQualityReviews,
    candidateQualityReviewsLoading,
    candidateQualityReviewsError,
    candidateResearchContracts,
    candidateResearchContractsLoading,
    candidateResearchContractsError,
    candidateResearchApprovalLoading,
    candidateResearchApprovalError,
    candidateResearchExecutionLoading,
    candidateResearchExecutionError,
    candidateImprovementProposals,
    candidateImprovementProposalsLoading,
    candidateImprovementProposalsError,
    candidateImprovementApplyLoading,
    candidateImprovementApplyError,
    candidateHarnessReports,
    candidateHarnessReportsLoading,
    candidateHarnessReportsError,
    skillImportPreview,
    skillImportPreviewLoading,
    skillImportPreviewError,
    skillImportCandidateCreateLoading,
    skillImportCandidateCreateError,
  } = useAppSelector((s) => s.skills);
  const {
    skills: regSkills,
    loading: regLoading,
    stats: regStats,
    detail: regDetail,
    detailLoading: regDetailLoading,
  } = useAppSelector((s) => s.skillRegistry);
  const localSkills = Object.values(items);
  const skillCandidates = Object.values(candidates);

  const [selection, setSelection] = useState<Selection>(null);
  const [searchFilter, setSearchFilter] = useState('');
  const [collapsedCats, setCollapsedCats] = useState<Record<string, boolean>>({});

  const [contentView, setContentView] = useState<'preview' | 'raw'>('preview');
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<SkillForm>(emptyForm);
  const [formSource, setFormSource] = useState<'local' | 'registry'>('local');
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string }>({ open: false, message: '' });
  const [builderPreview, setBuilderPreview] = useState<SkillPreviewData | null>(null);
  const [builderOpen, setBuilderOpen] = useState(false);
  const [importSourceFormat, setImportSourceFormat] = useState('markdown_prompt_pack');
  const [importName, setImportName] = useState('');
  const [importAuthor, setImportAuthor] = useState('unknown');
  const [importLicense, setImportLicense] = useState('unknown');
  const [importSourceUrl, setImportSourceUrl] = useState('');
  const [importContent, setImportContent] = useState('');
  const [importDiffOpen, setImportDiffOpen] = useState(false);
  const [candidateDetailExpanded, setCandidateDetailExpanded] = useState<Record<string, boolean>>({
    validation: false,
    requirements: false,
    contract: false,
    research: true,
    harness: true,
    source: false,
    content: false,
    improvement: true,
    improvementDiff: false,
  });


  const handleBuilderPreview = useCallback((data: SkillPreviewData | null) => {
    setBuilderPreview(data);
    if (data) {
      setSelection({ type: 'builder-preview' });
    } else if (selection?.type === 'builder-preview') {
      setSelection(null);
    }
  }, [selection]);

  const handleBuilderSaved = useCallback((message: string) => {
    setSnackbar({ open: true, message });
    dispatch(fetchSkillCandidates());
  }, [dispatch]);

  useEffect(() => {
    dispatch(fetchSkills());
    dispatch(fetchSkillCandidates());
    dispatch(fetchSkillRegistryStats());
    dispatch(fetchAllRegistrySkills());
  }, [dispatch]);

  // Group registry skills by category
  const regGrouped = useMemo(() => {
    const groups: Record<string, RegistrySkill[]> = {};
    const q = searchFilter.toLowerCase();
    for (const sk of regSkills) {
      if (q && !sk.name.toLowerCase().includes(q) && !sk.description.toLowerCase().includes(q)) continue;
      const cat = sk.category || 'General';
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(sk);
    }
    return groups;
  }, [regSkills, searchFilter]);

  const filteredLocal = useMemo(() => {
    const q = searchFilter.toLowerCase();
    if (!q) return localSkills;
    return localSkills.filter((s) => s.name.toLowerCase().includes(q) || s.description.toLowerCase().includes(q));
  }, [localSkills, searchFilter]);

  const filteredCandidates = useMemo(() => {
    const q = searchFilter.toLowerCase();
    if (!q) return skillCandidates;
    return skillCandidates.filter((candidate) => {
      const spec = candidate.skill_spec;
      return spec.name.toLowerCase().includes(q) || spec.description.toLowerCase().includes(q);
    });
  }, [skillCandidates, searchFilter]);

  const categoryOrder = useMemo(() => Object.keys(regGrouped).sort(), [regGrouped]);

  const toggleCategory = (cat: string) =>
    setCollapsedCats((p) => ({ ...p, [cat]: !p[cat] }));

  // Selection handlers
  const selectRegistry = (name: string) => {
    setSelection({ type: 'registry', name });
    dispatch(fetchSkillDetail(name));
  };

  const selectLocal = (id: string) => {
    setSelection({ type: 'local', id });
  };

  const selectCandidate = (id: string) => {
    setSelection({ type: 'candidate', id });
  };

  // Get active detail content
  const selectedLocal: Skill | null =
    selection?.type === 'local' ? items[selection.id] ?? null : null;
  const selectedCandidate: SkillSpecCandidate | null =
    selection?.type === 'candidate' ? candidates[selection.id] ?? null : null;
  const selectedRequirementsContract: SkillCandidateRequirementsContract | null =
    selectedCandidate ? candidateRequirementsContracts[selectedCandidate.candidate_id] ?? null : null;
  const selectedRequirementsContractLoading =
    selectedCandidate ? !!candidateRequirementsContractsLoading[selectedCandidate.candidate_id] : false;
  const selectedRequirementsContractError =
    selectedCandidate ? candidateRequirementsContractsError[selectedCandidate.candidate_id] ?? null : null;
  const selectedQualityReview: SkillCandidateQualityReview | null =
    selectedCandidate ? candidateQualityReviews[selectedCandidate.candidate_id] ?? null : null;
  const selectedQualityReviewLoading =
    selectedCandidate ? !!candidateQualityReviewsLoading[selectedCandidate.candidate_id] : false;
  const selectedQualityReviewError =
    selectedCandidate ? candidateQualityReviewsError[selectedCandidate.candidate_id] ?? null : null;
  const selectedResearchContract: SkillCandidateResearchContract | null =
    selectedCandidate ? candidateResearchContracts[selectedCandidate.candidate_id] ?? null : null;
  const selectedResearchContractLoading =
    selectedCandidate ? !!candidateResearchContractsLoading[selectedCandidate.candidate_id] : false;
  const selectedResearchContractError =
    selectedCandidate ? candidateResearchContractsError[selectedCandidate.candidate_id] ?? null : null;
  const selectedResearchApprovalLoading =
    selectedCandidate ? !!candidateResearchApprovalLoading[selectedCandidate.candidate_id] : false;
  const selectedResearchApprovalError =
    selectedCandidate ? candidateResearchApprovalError[selectedCandidate.candidate_id] ?? null : null;
  const selectedResearchExecutionLoading =
    selectedCandidate ? !!candidateResearchExecutionLoading[selectedCandidate.candidate_id] : false;
  const selectedResearchExecutionError =
    selectedCandidate ? candidateResearchExecutionError[selectedCandidate.candidate_id] ?? null : null;
  const selectedImprovementProposal: SkillCandidateImprovementProposal | null =
    selectedCandidate ? candidateImprovementProposals[selectedCandidate.candidate_id] ?? null : null;
  const selectedImprovementProposalLoading =
    selectedCandidate ? !!candidateImprovementProposalsLoading[selectedCandidate.candidate_id] : false;
  const selectedImprovementProposalError =
    selectedCandidate ? candidateImprovementProposalsError[selectedCandidate.candidate_id] ?? null : null;
  const selectedImprovementApplyLoading =
    selectedCandidate ? !!candidateImprovementApplyLoading[selectedCandidate.candidate_id] : false;
  const selectedImprovementApplyError =
    selectedCandidate ? candidateImprovementApplyError[selectedCandidate.candidate_id] ?? null : null;
  const selectedHarnessReport: SkillHarnessFullReport | null =
    selectedCandidate ? candidateHarnessReports[selectedCandidate.candidate_id] ?? null : null;
  const selectedHarnessLoading =
    selectedCandidate ? !!candidateHarnessReportsLoading[selectedCandidate.candidate_id] : false;
  const selectedHarnessError =
    selectedCandidate ? candidateHarnessReportsError[selectedCandidate.candidate_id] ?? null : null;
  const selectedReg: RegistrySkillDetail | null =
    selection?.type === 'registry' && regDetail?.name === selection.name ? regDetail : null;

  useEffect(() => {
    if (!selectedCandidate) return;
    if (candidateRequirementsContracts[selectedCandidate.candidate_id]) return;
    if (candidateRequirementsContractsLoading[selectedCandidate.candidate_id]) return;
    dispatch(fetchSkillCandidateRequirementsContract(selectedCandidate.candidate_id));
  }, [candidateRequirementsContracts, candidateRequirementsContractsLoading, dispatch, selectedCandidate]);

  useEffect(() => {
    if (!selectedCandidate) return;
    if (candidateQualityReviews[selectedCandidate.candidate_id]) return;
    if (candidateQualityReviewsLoading[selectedCandidate.candidate_id]) return;
    dispatch(fetchSkillCandidateQualityReview(selectedCandidate.candidate_id));
  }, [candidateQualityReviews, candidateQualityReviewsLoading, dispatch, selectedCandidate]);

  useEffect(() => {
    if (!selectedCandidate) return;
    if (candidateResearchContracts[selectedCandidate.candidate_id]) return;
    if (candidateResearchContractsLoading[selectedCandidate.candidate_id]) return;
    dispatch(fetchSkillCandidateResearchContract(selectedCandidate.candidate_id));
  }, [candidateResearchContracts, candidateResearchContractsLoading, dispatch, selectedCandidate]);

  useEffect(() => {
    if (!selectedCandidate) return;
    if (candidateImprovementProposals[selectedCandidate.candidate_id]) return;
    if (candidateImprovementProposalsLoading[selectedCandidate.candidate_id]) return;
    dispatch(fetchSkillCandidateImprovementProposal(selectedCandidate.candidate_id));
  }, [candidateImprovementProposals, candidateImprovementProposalsLoading, dispatch, selectedCandidate]);

  useEffect(() => {
    if (!selectedCandidate) return;
    if (candidateHarnessReports[selectedCandidate.candidate_id]) return;
    if (candidateHarnessReportsLoading[selectedCandidate.candidate_id]) return;
    dispatch(fetchSkillCandidateHarnessFull(selectedCandidate.candidate_id));
  }, [candidateHarnessReports, candidateHarnessReportsLoading, dispatch, selectedCandidate]);

  // CRUD
  const openCreate = () => {
    setEditingId(null);
    setFormSource('local');
    setForm(emptyForm);
    setDialogOpen(true);
  };

  const openEdit = (skill: Skill) => {
    setEditingId(skill.id);
    setFormSource('local');
    setForm({ name: skill.name, description: skill.description, content: skill.content, command: skill.command });
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (editingId) {
      await dispatch(updateSkill({ id: editingId, ...form }));
    } else if (formSource === 'registry') {
      await dispatch(createSkillCandidate({
        skill_spec: {
          name: form.name,
          description: form.description,
          content: form.content,
          command: form.command,
          source_format: 'openswarm_skill_registry_edited',
          metadata_confidence: 'inferred',
        },
        source: 'skill_registry_edit',
        source_ref: form.name,
      })).unwrap();
      dispatch(fetchSkillCandidates());
      setSnackbar({ open: true, message: `Skill candidate "${form.name}" saved for review` });
    } else {
      await dispatch(createSkill(form));
    }
    setDialogOpen(false);
  };

  const handleDelete = async (id: string) => {
    await dispatch(deleteSkill(id));
    if (selection?.type === 'local' && selection.id === id) setSelection(null);
  };

  const handleInstall = async () => {
    if (!selectedReg) return;
    await dispatch(createSkillCandidate({
      skill_spec: {
        name: selectedReg.name,
        description: selectedReg.description,
        content: selectedReg.content,
        command: selectedReg.name.toLowerCase().replace(/\s+/g, '-'),
        source_format: 'openswarm_skill_registry',
        metadata_confidence: 'inferred',
        provenance: {
          registry_name: selectedReg.name,
          registry_folder: selectedReg.folder,
          repository_url: selectedReg.repositoryUrl,
        },
        categories: selectedReg.category ? [selectedReg.category] : [],
      },
      source: 'skill_registry',
      source_ref: selectedReg.name,
    })).unwrap();
    dispatch(fetchSkillCandidates());
    setSnackbar({ open: true, message: `Skill candidate "${selectedReg.name}" saved for review` });
  };

  const handleEditInstall = () => {
    if (!selectedReg) return;
    setEditingId(null);
    setFormSource('registry');
    setForm({
      name: selectedReg.name,
      description: selectedReg.description,
      content: selectedReg.content,
      command: selectedReg.name.toLowerCase().replace(/\s+/g, '-'),
    });
    setDialogOpen(true);
  };

  const handleApproveCandidateInstall = async () => {
    if (!selectedCandidate) return;
    try {
      const result = await dispatch(approveSkillCandidate({ candidateId: selectedCandidate.candidate_id, approved: true })).unwrap();
      if (result.install_approved) {
        setSnackbar({ open: true, message: `Candidate "${result.skill_spec.name}" approved for install` });
      } else {
        setSnackbar({ open: true, message: `Candidate "${result.skill_spec.name}" is blocked by validation or policy gate` });
      }
    } catch (err) {
      console.error('Failed to approve skill candidate:', err);
      setSnackbar({ open: true, message: 'Failed to approve skill candidate' });
    }
  };

  const handleInstallCandidate = async () => {
    if (!selectedCandidate) return;
    try {
      const result = await dispatch(installSkillCandidate(selectedCandidate.candidate_id)).unwrap();
      setSnackbar({ open: true, message: `Installed "${result.skill.name}" as a local skill` });
    } catch (err) {
      console.error('Failed to install skill candidate:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to install skill candidate' });
    }
  };

  const handleRejectCandidate = async () => {
    if (!selectedCandidate) return;
    try {
      const result = await dispatch(rejectSkillCandidate(selectedCandidate.candidate_id)).unwrap();
      setSnackbar({ open: true, message: `Rejected "${result.skill_spec.name}"` });
    } catch (err) {
      console.error('Failed to reject skill candidate:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to reject skill candidate' });
    }
  };

  const handleDeleteCandidate = async () => {
    if (!selectedCandidate) return;
    const candidateName = selectedCandidate.skill_spec.name || 'Untitled Skill Candidate';
    try {
      await dispatch(deleteSkillCandidate(selectedCandidate.candidate_id)).unwrap();
      if (selection?.type === 'candidate' && selection.id === selectedCandidate.candidate_id) {
        setSelection(null);
      }
      setSnackbar({ open: true, message: `Deleted "${candidateName}"` });
    } catch (err) {
      console.error('Failed to delete skill candidate:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to delete skill candidate' });
    }
  };


  const handleApproveCandidateResearch = async (approved: boolean) => {
    if (!selectedCandidate) return;
    try {
      const result = await dispatch(approveSkillCandidateResearch({
        candidateId: selectedCandidate.candidate_id,
        approved,
      })).unwrap();
      setSnackbar({
        open: true,
        message: approved
          ? `Research permission allowed for "${result.candidate.skill_spec.name}". No web research was executed.`
          : `Research permission revoked for "${result.candidate.skill_spec.name}".`,
      });
    } catch (err) {
      console.error('Failed to update skill candidate research permission:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to update research permission' });
    }
  };

  const handleExecuteCandidateResearch = async () => {
    if (!selectedCandidate) return;
    try {
      const result = await dispatch(executeSkillCandidateResearch(selectedCandidate.candidate_id)).unwrap();
      setSnackbar({
        open: true,
        message: `Research evidence saved for "${result.candidate.skill_spec.name}". Candidate content was not changed.`,
      });
      dispatch(fetchSkillCandidateImprovementProposal(selectedCandidate.candidate_id));
    } catch (err) {
      console.error('Failed to execute skill candidate research:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to execute research' });
    }
  };


  const handleApplyCandidateImprovement = async () => {
    if (!selectedCandidate) return;
    try {
      const result = await dispatch(applySkillCandidateImprovementProposal({
        candidateId: selectedCandidate.candidate_id,
        approved: true,
      })).unwrap();
      setSnackbar({ open: true, message: `Applied improvement proposal to "${result.candidate.skill_spec.name}"` });
      dispatch(fetchSkillCandidateQualityReview(selectedCandidate.candidate_id));
      dispatch(fetchSkillCandidateImprovementProposal(selectedCandidate.candidate_id));
    } catch (err) {
      console.error('Failed to apply skill candidate improvement proposal:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to apply improvement proposal' });
    }
  };

  const buildImportPayload = () => ({
    source_format: importSourceFormat || 'unknown',
    source_author: importAuthor || 'unknown',
    source_license: importLicense || 'unknown',
    source_url: importSourceUrl || '',
    name: importName || 'Imported Skill',
    content: importContent,
  });

  const handlePreviewImport = async () => {
    try {
      await dispatch(previewSkillImport(buildImportPayload())).unwrap();
      setSnackbar({ open: true, message: 'Skill import preview generated. Nothing was installed.' });
    } catch (err) {
      console.error('Failed to preview skill import:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to preview skill import' });
    }
  };

  const handleCreateImportCandidate = async () => {
    try {
      const result = await dispatch(createSkillCandidateFromImport(buildImportPayload())).unwrap();
      setSelection({ type: 'candidate', id: result.candidate.candidate_id });
      dispatch(fetchSkillCandidates());
      setSnackbar({ open: true, message: `Skill candidate "${result.candidate.skill_spec.name}" created from import preview` });
    } catch (err) {
      console.error('Failed to create import candidate:', err);
      setSnackbar({ open: true, message: err instanceof Error ? err.message : 'Failed to create import candidate' });
    }
  };

  const isSelected = (type: 'registry' | 'local' | 'candidate', key: string) => {
    if (!selection) return false;
    if (type === 'registry') return selection.type === 'registry' && selection.name === key;
    if (type === 'candidate') return selection.type === 'candidate' && selection.id === key;
    return selection.type === 'local' && selection.id === key;
  };

  // ─── Content preview with raw/preview toggle ───
  const ContentPreview: React.FC<{ content: string }> = ({ content }) => (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <Box sx={{ display: 'flex', justifyContent: 'flex-end', mb: 1, flexShrink: 0 }}>
        <ToggleButtonGroup
          value={contentView}
          exclusive
          onChange={(_, v) => { if (v) setContentView(v); }}
          size="small"
          sx={{
            '& .MuiToggleButton-root': {
              color: c.text.tertiary, border: `1px solid ${c.border.medium}`,
              textTransform: 'none', fontSize: '0.74rem', py: 0.25, px: 1.2, lineHeight: 1.4,
              '&.Mui-selected': { bgcolor: c.bg.secondary, color: c.text.primary, borderColor: c.border.strong },
              '&:hover': { bgcolor: 'rgba(0,0,0,0.03)' },
            },
          }}
        >
          <ToggleButton value="preview"><VisibilityIcon sx={{ fontSize: 14, mr: 0.5 }} />Preview</ToggleButton>
          <ToggleButton value="raw"><CodeIcon sx={{ fontSize: 14, mr: 0.5 }} />Raw</ToggleButton>
        </ToggleButtonGroup>
      </Box>

      {contentView === 'raw' ? (
        <Box sx={{
          flex: 1, minHeight: 0,
          bgcolor: c.bg.secondary, border: `${c.border.width} solid ${c.border.subtle}`,
          borderRadius: `${c.radius.md}px`, p: 2.5,
          overflow: 'auto',
          '&::-webkit-scrollbar': { width: 5 },
          '&::-webkit-scrollbar-thumb': { background: c.border.medium, borderRadius: 3 },
        }}>
          <Typography component="pre" sx={{
            color: c.text.secondary, fontSize: '0.8rem', fontFamily: c.font.mono,
            whiteSpace: 'pre-wrap', wordBreak: 'break-word', m: 0, lineHeight: 1.65,
          }}>
            {content}
          </Typography>
        </Box>
      ) : (
        <Box sx={{
          flex: 1, minHeight: 0,
          bgcolor: c.bg.elevated, border: `${c.border.width} solid ${c.border.subtle}`,
          borderRadius: `${c.radius.md}px`, p: 3,
          overflow: 'auto',
          '&::-webkit-scrollbar': { width: 5 },
          '&::-webkit-scrollbar-thumb': { background: c.border.medium, borderRadius: 3 },
          '& h1': { fontSize: '1.3rem', fontWeight: 700, color: c.text.primary, mt: 0, mb: 1.5, fontFamily: c.font.sans },
          '& h2': { fontSize: '1.1rem', fontWeight: 600, color: c.text.primary, mt: 2, mb: 1, fontFamily: c.font.sans },
          '& h3': { fontSize: '0.95rem', fontWeight: 600, color: c.text.primary, mt: 1.5, mb: 0.75, fontFamily: c.font.sans },
          '& p': { fontSize: '0.88rem', color: c.text.secondary, lineHeight: 1.7, mb: 1.5 },
          '& ul, & ol': { pl: 2.5, mb: 1.5, '& li': { fontSize: '0.88rem', color: c.text.secondary, lineHeight: 1.7, mb: 0.5 } },
          '& code': { fontFamily: c.font.mono, fontSize: '0.82rem', bgcolor: 'rgba(0,0,0,0.04)', px: 0.5, py: 0.15, borderRadius: `${c.radius.xs}px` },
          '& pre': { bgcolor: c.bg.secondary, border: `${c.border.width} solid ${c.border.subtle}`, borderRadius: `${c.radius.sm}px`, p: 2, mb: 1.5, overflow: 'auto',
            '& code': { bgcolor: 'transparent', color: c.text.secondary, px: 0, py: 0 },
          },
          '& hr': { border: 'none', borderTop: `1px solid ${c.border.subtle}`, my: 2 },
          '& a': { color: c.accent.primary, textDecoration: 'none', '&:hover': { textDecoration: 'underline' } },
          '& strong': { fontWeight: 600, color: c.text.primary },
        }}>
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
        </Box>
      )}
    </Box>
  );

  // ─── Sidebar row component ───
  const SidebarRow: React.FC<{
    label: string;
    selected: boolean;
    onClick: () => void;
    icon?: React.ReactNode;
  }> = ({ label, selected, onClick, icon }) => (
    <Box
      onClick={onClick}
      sx={{
        display: 'flex', alignItems: 'center', gap: 1, px: 1.5, py: 0.6,
        borderRadius: `${c.radius.sm}px`, cursor: 'pointer',
        bgcolor: selected ? c.bg.secondary : 'transparent',
        transition: 'background 0.12s',
        '&:hover': { bgcolor: selected ? c.bg.secondary : 'rgba(0,0,0,0.03)' },
      }}
    >
      {icon ?? <DescriptionIcon sx={{ fontSize: 15, color: c.text.tertiary, flexShrink: 0 }} />}
      <Typography
        sx={{
          fontSize: '0.82rem', color: selected ? c.text.primary : c.text.secondary,
          fontWeight: selected ? 600 : 400, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
        }}
      >
        {label}
      </Typography>
    </Box>
  );

  const toDisplayText = (value: unknown, fallback = '—') => {
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    return fallback;
  };

  const getGateStatus = (warning: Record<string, any>) => {
    const status = toDisplayText(warning.status, '').toLowerCase();
    if (['blocked', 'failed', 'denied', 'rejected'].some((token) => status.includes(token))) {
      return { label: toDisplayText(warning.status, 'blocked'), color: c.status.error, bg: c.status.errorBg };
    }
    if (['passed', 'approved', 'ok', 'allowed'].some((token) => status.includes(token))) {
      return { label: toDisplayText(warning.status, 'passed'), color: c.status.success, bg: c.status.successBg };
    }
    return { label: toDisplayText(warning.status, 'warning'), color: c.status.warning, bg: c.status.warningBg };
  };

  const asArray = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);

  const isPlainObject = (value: unknown): value is Record<string, unknown> =>
    !!value && typeof value === 'object' && !Array.isArray(value);

  const toCompactValue = (value: unknown) => {
    if (typeof value === 'string' && value.trim()) return value;
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) {
      const compact = value.map((item) => toDisplayText(item, '')).filter(Boolean).join(', ');
      return compact || '[]';
    }
    if (isPlainObject(value)) {
      try {
        return JSON.stringify(value);
      } catch {
        return '[object]';
      }
    }
    return '—';
  };

  const getInstallDisabledReason = (candidate: SkillSpecCandidate) => {
    if (candidate.status === 'installed') return 'Already installed.';
    if (candidate.status === 'rejected') return 'Rejected candidates cannot be installed.';
    if (!candidate.install_approved) return 'Approve install before installing.';
    return 'Ready to install.';
  };

  const ReviewSection: React.FC<{
    title: string;
    tone?: 'default' | 'success' | 'warning' | 'error';
    children: React.ReactNode;
  }> = ({ title, tone = 'default', children }) => {
    const toneColor = tone === 'success'
      ? c.status.success
      : tone === 'warning'
        ? c.status.warning
        : tone === 'error'
          ? c.status.error
          : c.text.secondary;

    return (
      <Box
        sx={{
          p: 1.5,
          borderRadius: `${c.radius.sm}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.page,
          minWidth: 0,
        }}
      >
        <Typography sx={{ fontSize: '0.74rem', color: toneColor, mb: 1, fontWeight: 700, letterSpacing: 0.1 }}>
          {title}
        </Typography>
        {children}
      </Box>
    );
  };

  const EmptyReviewState: React.FC<{ text: string; tone?: 'success' | 'default' }> = ({ text, tone = 'default' }) => (
    <Typography
      sx={{
        fontSize: '0.76rem',
        color: tone === 'success' ? c.status.success : c.text.ghost,
        lineHeight: 1.5,
      }}
    >
      {text}
    </Typography>
  );

  const MetaChip: React.FC<{ label: string; tone?: 'default' | 'success' | 'warning' | 'error' }> = ({ label, tone = 'default' }) => {
    const chipTone = tone === 'success'
      ? { color: c.status.success, bg: c.status.successBg }
      : tone === 'warning'
        ? { color: c.status.warning, bg: c.status.warningBg }
        : tone === 'error'
          ? { color: c.status.error, bg: c.status.errorBg }
          : { color: c.text.muted, bg: c.bg.secondary };

    return (
      <Chip
        label={label}
        size="small"
        sx={{
          bgcolor: chipTone.bg,
          color: chipTone.color,
          fontSize: '0.68rem',
          height: 21,
          border: `1px solid ${c.border.subtle}`,
          '& .MuiChip-label': { px: 0.8 },
        }}
      />
    );
  };


  const SkillResearchContractPanel: React.FC<{
    contract: SkillCandidateResearchContract | null;
    loading: boolean;
    error: string | null;
    approvalLoading: boolean;
    approvalError: string | null;
    executionLoading: boolean;
    executionError: string | null;
    onSetResearchPermission: (approved: boolean) => void;
    onExecuteResearch: () => void;
  }> = ({ contract, loading, error, approvalLoading, approvalError, executionLoading, executionError, onSetResearchPermission, onExecuteResearch }) => {
    const requiresResearch = contract?.requires_web_research === true;
    const researchAllowed = contract?.research_allowed === true;
    const webExecuted = contract?.web_research_executed === true;
    const readOnly = contract?.can_mutate_candidate !== true
      && contract?.can_install_skill !== true
      && contract?.can_activate_tools !== true
      && contract?.can_activate_mcp !== true;
    const queries = Array.isArray(contract?.research_queries) ? contract.research_queries : [];
    const sourceTypes = Array.isArray(contract?.expected_source_types) ? contract.expected_source_types : [];
    const gaps = Array.isArray(contract?.research_gap_items) ? contract.research_gap_items : [];
    const guardrails = Array.isArray(contract?.guardrails) ? contract.guardrails : [];
    const canExecuteResearch = requiresResearch && researchAllowed && !webExecuted;
    const summary = requiresResearch
      ? 'This skill may need current external documentation before finalizing.'
      : 'No current-information dependency detected.';

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
        {error ? (
          <ReviewSection title="Research contract unavailable" tone="error">
            <EmptyReviewState text={error} />
          </ReviewSection>
        ) : !contract && loading ? (
          <ReviewSection title="Loading research contract">
            <EmptyReviewState text="Checking whether this candidate depends on current external information..." />
          </ReviewSection>
        ) : !contract ? (
          <ReviewSection title="No research contract loaded">
            <EmptyReviewState text="No research contract is available for this candidate." />
          </ReviewSection>
        ) : (
          <>
            <ReviewSection title="Summary" tone={requiresResearch ? 'warning' : 'success'}>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary, lineHeight: 1.5, mb: 1 }}>
                {toDisplayText(contract.summary, summary)}
              </Typography>
              <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.45, mb: 1 }}>
                {summary}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
                <MetaChip label={requiresResearch ? 'Research needed' : 'No research needed'} tone={requiresResearch ? 'warning' : 'success'} />
                {researchAllowed ? <MetaChip label="Research allowed" tone="success" /> : <MetaChip label="Research not allowed yet" tone="warning" />}
                {!webExecuted && <MetaChip label="Web not executed" tone={requiresResearch ? 'warning' : 'default'} />}
                {readOnly && <MetaChip label="Read-only" tone="success" />}
              </Box>
            </ReviewSection>



            {requiresResearch && (
              <ReviewSection title="Research permission" tone={researchAllowed ? 'success' : 'warning'}>
                <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.45, mb: 1 }}>
                  This only authorizes a future research phase for this candidate. It does not browse, execute web research, install the skill, apply improvements, activate tools, or activate MCP.
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                  {researchAllowed ? (
                    <>
                      <MetaChip label="Research allowed" tone="success" />
                      <Button
                        variant="outlined"
                        size="small"
                        disabled={approvalLoading}
                        onClick={() => onSetResearchPermission(false)}
                        sx={{ textTransform: 'none', borderRadius: `${c.radius.md}px`, fontSize: '0.74rem' }}
                      >
                        Revoke research permission
                      </Button>
                    </>
                  ) : (
                    <Button
                      variant="contained"
                      size="small"
                      disabled={approvalLoading}
                      onClick={() => onSetResearchPermission(true)}
                      startIcon={approvalLoading ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : undefined}
                      sx={{
                        bgcolor: c.accent.primary,
                        '&:hover': { bgcolor: c.accent.pressed },
                        textTransform: 'none',
                        borderRadius: `${c.radius.md}px`,
                        fontSize: '0.74rem',
                        boxShadow: 'none',
                      }}
                    >
                      Allow research for this candidate
                    </Button>
                  )}
                </Box>
                {approvalError && (
                  <Typography sx={{ fontSize: '0.72rem', color: c.status.error, lineHeight: 1.4, mt: 0.8 }}>
                    {approvalError}
                  </Typography>
                )}
              </ReviewSection>
            )}

            {requiresResearch && researchAllowed && (
              <ReviewSection title="Research execution" tone={webExecuted ? 'success' : 'warning'}>
                <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.45, mb: 1 }}>
                  This runs approved web research and stores evidence on the candidate. It does not change candidate content, install the skill, apply improvements, activate tools, or activate MCP.
                </Typography>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, alignItems: 'center' }}>
                  {webExecuted ? (
                    <MetaChip label="Research evidence saved" tone="success" />
                  ) : (
                    <Button
                      variant="contained"
                      size="small"
                      disabled={!canExecuteResearch || executionLoading}
                      onClick={onExecuteResearch}
                      startIcon={executionLoading ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : undefined}
                      sx={{
                        bgcolor: c.accent.primary,
                        '&:hover': { bgcolor: c.accent.pressed },
                        textTransform: 'none',
                        borderRadius: `${c.radius.md}px`,
                        fontSize: '0.74rem',
                        boxShadow: 'none',
                      }}
                    >
                      Run approved research
                    </Button>
                  )}
                </Box>
                {executionError && (
                  <Typography sx={{ fontSize: '0.72rem', color: c.status.error, lineHeight: 1.4, mt: 0.8 }}>
                    {executionError}
                  </Typography>
                )}
              </ReviewSection>
            )}

            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 1.25 }}>
              <ReviewSection title="Research queries" tone={queries.length > 0 ? 'warning' : 'default'}>
                <ChipList values={queries} empty="No research queries suggested." tone="warning" />
              </ReviewSection>

              <ReviewSection title="Expected source types" tone={sourceTypes.length > 0 ? 'warning' : 'default'}>
                <ChipList values={sourceTypes} empty="No source types specified." />
              </ReviewSection>

              <ReviewSection title="Next step" tone={requiresResearch ? 'warning' : 'success'}>
                <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.45 }}>
                  {toDisplayText(contract.next_step, requiresResearch ? 'Review the suggested sources before finalizing this skill.' : 'No external research step is required.')}
                </Typography>
              </ReviewSection>

              <ReviewSection title="Research gaps" tone={gaps.length > 0 ? 'warning' : 'success'}>
                <ChipList values={gaps} empty="No research gaps detected." tone="warning" />
              </ReviewSection>

              <Box sx={{ gridColumn: { xs: 'auto', lg: '1 / -1' } }}>
                <ReviewSection title="Guardrails" tone="success">
                  {guardrails.length > 0 ? (
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                      {guardrails.map((guardrail, index) => (
                        <Typography key={`research-guardrail-${index}`} sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.4 }}>
                          {toDisplayText(guardrail)}
                        </Typography>
                      ))}
                    </Box>
                  ) : (
                    <EmptyReviewState text="Read-only contract: no candidate mutation, install, tool activation, or MCP activation." tone="success" />
                  )}
                </ReviewSection>
              </Box>
            </Box>
          </>
        )}
      </Box>
    );
  };

  const SkillImprovementProposalPanel: React.FC<{
    proposal: SkillCandidateImprovementProposal | null;
    loading: boolean;
    error: string | null;
    applyLoading: boolean;
    applyError: string | null;
    onApply: () => void;
  }> = ({ proposal, loading, error, applyLoading, applyError, onApply }) => {
    const items = asArray(proposal?.proposal_items) as Record<string, unknown>[];
    const canGenerateDiff = !!proposal?.can_generate_diff;
    const requiresWebResearch = !!proposal?.requires_web_research;
    const diff = toDisplayText(proposal?.preview_diff, '');
    const proposedContent = toDisplayText(proposal?.proposed_content, '');

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.25 }}>
        {error ? (
          <ReviewSection title="Improvement proposal unavailable" tone="error">
            <EmptyReviewState text={error} />
          </ReviewSection>
        ) : !proposal && loading ? (
          <ReviewSection title="Loading improvement proposal">
            <EmptyReviewState text="Building review-based improvement proposal..." />
          </ReviewSection>
        ) : !proposal ? (
          <ReviewSection title="No proposal loaded">
            <EmptyReviewState text="No improvement proposal is available for this candidate." />
          </ReviewSection>
        ) : (
          <>
            <ReviewSection title="Proposal summary" tone={items.length > 0 ? 'warning' : 'success'}>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary, lineHeight: 1.5, mb: 1 }}>
                {toDisplayText(proposal.summary, 'No proposal summary available.')}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65, mb: 1 }}>
                <MetaChip label={`${proposal.item_count ?? items.length} proposed changes`} tone={items.length > 0 ? 'warning' : 'success'} />
                <MetaChip label={canGenerateDiff ? 'Diff preview ready' : 'No diff'} tone={canGenerateDiff ? 'success' : 'default'} />
                <MetaChip label="Apply requires explicit action" tone="warning" />
                {requiresWebResearch && <MetaChip label="Research recommended" tone="warning" />}
              </Box>
              <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, lineHeight: 1.45 }}>
                Applying this proposal updates only the candidate content. It does not install, approve install, activate tools, activate MCP, or grant permissions.
              </Typography>
            </ReviewSection>

            <ReviewSection title="Proposed improvements" tone={items.length > 0 ? 'warning' : 'success'}>
              {items.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                  {items.slice(0, 8).map((item, index) => (
                    <Box
                      key={`proposal-item-${index}`}
                      sx={{
                        p: 1,
                        borderRadius: `${c.radius.sm}px`,
                        border: `1px solid ${c.border.subtle}`,
                        bgcolor: c.bg.page,
                      }}
                    >
                      <Typography sx={{ fontSize: '0.76rem', color: c.text.primary, fontWeight: 700 }}>
                        {toDisplayText(item.title, toDisplayText(item.code, 'Improvement'))}
                      </Typography>
                      <Typography sx={{ fontSize: '0.7rem', color: c.text.ghost, mt: 0.35 }}>
                        {toDisplayText(item.source, 'review')} · {toDisplayText(item.target_section, 'SKILL.md')}
                      </Typography>
                      <Typography sx={{ fontSize: '0.73rem', color: c.text.secondary, mt: 0.5, lineHeight: 1.45 }}>
                        {toDisplayText(item.proposed_change, 'No proposed change text.')}
                      </Typography>
                    </Box>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No improvements proposed." tone="success" />
              )}
            </ReviewSection>

            <CollapsibleCandidatePanel
              id="improvementDiff"
              title="Improvement diff preview"
              summary="Read-only proposed SKILL.md changes. Nothing is applied until you confirm."
              defaultTone={canGenerateDiff ? 'warning' : 'default'}
            >
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                <Typography
                  component="pre"
                  sx={{
                    m: 0,
                    p: 1.25,
                    maxHeight: 280,
                    overflow: 'auto',
                    borderRadius: `${c.radius.sm}px`,
                    border: `1px solid ${c.border.subtle}`,
                    bgcolor: c.bg.page,
                    color: c.text.secondary,
                    fontFamily: c.font.mono,
                    fontSize: '0.7rem',
                    whiteSpace: 'pre-wrap',
                    lineHeight: 1.45,
                  }}
                >
                  {diff || 'No diff available.'}
                </Typography>
                <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost }}>
                  Proposed content length: {proposedContent.length} characters.
                </Typography>
              </Box>
            </CollapsibleCandidatePanel>

            {applyError && (
              <Alert severity="error" sx={{ borderRadius: `${c.radius.md}px` }}>
                {applyError}
              </Alert>
            )}

            <Box sx={{ display: 'flex', justifyContent: 'flex-end' }}>
              <Tooltip title={canGenerateDiff ? 'Apply proposed content to this candidate only. This does not install the skill.' : 'No diff available to apply.'}>
                <span>
                  <Button
                    variant="contained"
                    size="small"
                    disabled={!canGenerateDiff || applyLoading}
                    onClick={onApply}
                    startIcon={applyLoading ? <CircularProgress size={14} sx={{ color: 'inherit' }} /> : <AutoFixHighIcon sx={{ fontSize: 16 }} />}
                    sx={{
                      bgcolor: c.accent.primary,
                      '&:hover': { bgcolor: c.accent.pressed },
                      textTransform: 'none',
                      borderRadius: `${c.radius.md}px`,
                      px: 2,
                      py: 0.6,
                      fontSize: '0.78rem',
                      fontWeight: 700,
                      boxShadow: 'none',
                    }}
                  >
                    Apply improvement to candidate
                  </Button>
                </span>
              </Tooltip>
            </Box>
          </>
        )}
      </Box>
    );
  };

  const CollapsibleCandidatePanel: React.FC<{
    id: string;
    title: string;
    summary: string;
    defaultTone?: 'default' | 'success' | 'warning' | 'error';
    children: React.ReactNode;
  }> = ({ id, title, summary, defaultTone = 'default', children }) => {
    const expanded = !!candidateDetailExpanded[id];

    return (
      <Box
        sx={{
          mb: 1.25,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
          overflow: 'hidden',
          flexShrink: 0,
        }}
      >
        <Box
          onClick={() => setCandidateDetailExpanded((prev) => ({ ...prev, [id]: !expanded }))}
          sx={{
            px: 2,
            py: 1.25,
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 1.5,
            '&:hover': { bgcolor: c.bg.elevated },
          }}
        >
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700 }}>
              {title}
            </Typography>
            <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, mt: 0.25, lineHeight: 1.35 }}>
              {summary}
            </Typography>
          </Box>
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.65, flexShrink: 0 }}>
            <MetaChip label={expanded ? 'Hide details' : 'Show details'} tone={defaultTone} />
          </Box>
        </Box>
        <Collapse in={expanded}>
          <Box sx={{ px: 2, pb: 2 }}>
            {children}
          </Box>
        </Collapse>
      </Box>
    );
  };

  const ChipList: React.FC<{ values: unknown; empty: string; tone?: 'default' | 'warning' | 'error' }> = ({ values, empty, tone = 'default' }) => {
    const items = asArray(values).filter((item) => toDisplayText(item, '').trim());

    if (items.length === 0) {
      return <EmptyReviewState text={empty} />;
    }

    return (
      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
        {items.map((item, index) => (
          <MetaChip
            key={`chip-${index}-${toCompactValue(item)}`}
            label={toCompactValue(item)}
            tone={tone === 'default' ? 'default' : tone}
          />
        ))}
      </Box>
    );
  };

  const SkillHarnessPanel: React.FC<{ report: SkillHarnessFullReport | null; loading: boolean; error: string | null }> = ({ report, loading, error }) => {
    const testContract = report?.test_contract || {};
    const dryRun = report?.dry_run || {};
    const validation = report?.runtime_validation || {};
    const evidence = report?.evidence_quality || {};
    const regression = report?.regression_suite || {};
    const promotion = report?.promotion_gate || {};
    const testCases = asArray(testContract.test_cases);
    const evaluated = asArray(dryRun.evaluated_test_cases);
    const checks = asArray(validation.checks);
    const regressions = asArray(regression.regression_tests);
    const reasons = asArray(promotion.reasons);
    const actions = asArray(promotion.required_actions);

    if (error) return <ReviewSection title="Skill harness unavailable" tone="error"><EmptyReviewState text={error} /></ReviewSection>;
    if (loading) return <ReviewSection title="Loading skill harness"><EmptyReviewState text="Loading read-only harness contracts..." /></ReviewSection>;
    if (!report) return <ReviewSection title="Skill harness"><EmptyReviewState text="No harness report loaded." /></ReviewSection>;

    return (
      <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
          <MetaChip label="read-only" tone="success" />
          <MetaChip label="no execution" tone="success" />
          <MetaChip label="no install" tone="warning" />
          <MetaChip label="tools/MCP disabled" tone="warning" />
          <MetaChip label={`validation ${toDisplayText(validation.status, 'unmeasured')}`} tone={validation.status === 'passed' ? 'success' : validation.status === 'blocked' || validation.status === 'failed' ? 'error' : 'warning'} />
          <MetaChip label={`promotion ${toDisplayText(promotion.decision, 'unmeasured')}`} tone={promotion.decision === 'promote_ready' ? 'success' : promotion.decision === 'blocked' ? 'error' : 'warning'} />
        </Box>

        <ReviewSection title="Test cases" tone={testContract.status === 'blocked' ? 'error' : testContract.status === 'ready' ? 'success' : 'warning'}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
            <MetaChip label={`status ${toDisplayText(testContract.status, 'unmeasured')}`} />
            <MetaChip label={`cases ${toDisplayText(testContract.test_case_count, 0)}`} />
          </Box>
          {testCases.length > 0 ? testCases.slice(0, 4).map((raw, index) => {
            const item = isPlainObject(raw) ? raw : {};
            return (
              <Box key={`harness-case-${index}`} sx={{ mb: 0.65, pl: 0.75, borderLeft: `2px solid ${c.border.subtle}` }}>
                <Typography sx={{ fontSize: '0.7rem', color: c.text.secondary, fontWeight: 700 }}>{toDisplayText(item.title, 'test case')}</Typography>
                <Typography sx={{ fontSize: '0.66rem', color: c.text.ghost, lineHeight: 1.35 }}>{toDisplayText(item.expected_behavior, 'Expected behavior not provided')}</Typography>
              </Box>
            );
          }) : <EmptyReviewState text="No proposed test cases." />}
        </ReviewSection>

        <ReviewSection title="Dry run simulation" tone={dryRun.status === 'blocked' ? 'error' : dryRun.status === 'ready' ? 'success' : 'warning'}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
            <MetaChip label={toDisplayText(dryRun.dry_run_mode, 'read_only_simulation')} />
            <MetaChip label={dryRun.executed ? 'executed' : 'not executed'} tone={dryRun.executed ? 'error' : 'success'} />
            <MetaChip label={dryRun.tool_calls_executed ? 'tools executed' : 'no tool calls'} tone={dryRun.tool_calls_executed ? 'error' : 'success'} />
            <MetaChip label={dryRun.mcp_activated ? 'MCP activated' : 'MCP disabled'} tone={dryRun.mcp_activated ? 'error' : 'success'} />
          </Box>
          <ChipList values={evaluated.map((item) => isPlainObject(item) ? `${toDisplayText(item.test_case_id)}:${toDisplayText(item.status)}` : toDisplayText(item))} empty="No simulated cases" />
        </ReviewSection>

        <ReviewSection title="Runtime validation" tone={validation.status === 'passed' ? 'success' : validation.status === 'blocked' || validation.status === 'failed' ? 'error' : 'warning'}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
            <MetaChip label={`passed ${toDisplayText(validation.passed_count, 0)}`} tone="success" />
            <MetaChip label={`failed ${toDisplayText(validation.failed_count, 0)}`} tone={validation.failed_count ? 'error' : 'success'} />
            <MetaChip label={`warnings ${toDisplayText(validation.warning_count, 0)}`} tone={validation.warning_count ? 'warning' : 'success'} />
          </Box>
          <ChipList values={checks.slice(0, 8).map((item) => isPlainObject(item) ? `${toDisplayText(item.code)}:${toDisplayText(item.status)}` : toDisplayText(item))} empty="No validation checks" />
        </ReviewSection>

        <ReviewSection title="Evidence quality" tone={evidence.status === 'strong' || evidence.status === 'sufficient' ? 'success' : evidence.status === 'blocked' ? 'error' : 'warning'}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
            <MetaChip label={`status ${toDisplayText(evidence.status, 'unmeasured')}`} />
            <MetaChip label={`evidence ${toDisplayText(evidence.evidence_count, 0)}`} />
          </Box>
          <ChipList values={asArray(evidence.evidence_refs)} empty="No evidence refs present" />
          <Typography sx={{ mt: 0.6, fontSize: '0.67rem', color: c.text.ghost }}>
            Missing: {asArray(evidence.missing_evidence).map((item) => toDisplayText(item)).join(', ') || 'none'}
          </Typography>
        </ReviewSection>

        <ReviewSection title="Regression suite / Promotion gate" tone={promotion.decision === 'promote_ready' ? 'success' : promotion.decision === 'blocked' ? 'error' : 'warning'}>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
            <MetaChip label={`regression ${toDisplayText(regression.status, 'unmeasured')}`} />
            <MetaChip label={`tests ${regressions.length}`} />
            <MetaChip label={`decision ${toDisplayText(promotion.decision, 'unmeasured')}`} />
            <MetaChip label={promotion.can_request_install_approval ? 'can request approval' : 'approval request blocked'} tone={promotion.can_request_install_approval ? 'success' : 'warning'} />
          </Box>
          {reasons.length > 0 && <Typography sx={{ fontSize: '0.67rem', color: c.status.warning, lineHeight: 1.4 }}>Reasons: {reasons.map((item) => toDisplayText(isPlainObject(item) ? item.code : item)).join(', ')}</Typography>}
          {actions.length > 0 && <Typography sx={{ fontSize: '0.67rem', color: c.text.ghost, lineHeight: 1.4, mt: 0.35 }}>Required actions: {actions.map((item) => toDisplayText(isPlainObject(item) ? item.code : item)).join(', ')}</Typography>}
        </ReviewSection>
      </Box>
    );
  };

  const DetailRow: React.FC<{ label: string; value: unknown; tone?: 'default' | 'success' | 'warning' | 'error' }> = ({ label, value, tone = 'default' }) => (
    <Box sx={{ minWidth: 0 }}>
      <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, mb: 0.35, fontWeight: 600 }}>
        {label}
      </Typography>
      <MetaChip label={toCompactValue(value)} tone={tone} />
    </Box>
  );

  const CandidateReview: React.FC<{ candidate: SkillSpecCandidate }> = ({ candidate }) => {
    const validationErrors = Array.isArray(candidate.validation_errors) ? candidate.validation_errors : [];
    const warnings = Array.isArray(candidate.warnings) ? candidate.warnings : [];
    const evidenceRefs = Array.isArray(candidate.evidence_refs) ? candidate.evidence_refs : [];
    const policyRefs = Array.isArray(candidate.policy_refs) ? candidate.policy_refs : [];
    const gateBlocked = validationErrors.length > 0 || warnings.some((warning) => {
      const status = toDisplayText(warning?.status, '').toLowerCase();
      return ['blocked', 'failed', 'denied', 'rejected'].some((token) => status.includes(token));
    });

    return (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
          flexShrink: 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1.5 }}>
          <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700 }}>
            Candidate review
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.75, justifyContent: 'flex-end' }}>
            <MetaChip
              label={gateBlocked ? 'Gate blocked' : 'Gate passed'}
              tone={gateBlocked ? 'error' : 'success'}
            />
            <MetaChip
              label={candidate.install_approved ? 'Install approved' : 'Install not approved'}
              tone={candidate.install_approved ? 'success' : 'warning'}
            />
          </Box>
        </Box>

        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 1.25 }}>
          <ReviewSection title="Validation errors" tone={validationErrors.length > 0 ? 'error' : 'success'}>
            {validationErrors.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                {validationErrors.map((item, index) => (
                  <Box
                    key={`validation-${index}`}
                    sx={{
                      p: 1,
                      borderRadius: `${c.radius.xs}px`,
                      border: `1px solid ${c.border.subtle}`,
                      bgcolor: c.bg.elevated,
                    }}
                  >
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.6, mb: 0.4 }}>
                      <Typography sx={{ fontSize: '0.76rem', color: c.text.primary, fontWeight: 650 }}>
                        {toDisplayText(item?.code, 'validation_error')}
                      </Typography>
                      {item?.severity != null && <MetaChip label={toDisplayText(item.severity, 'severity')} tone="error" />}
                    </Box>
                    <Typography sx={{ fontSize: '0.76rem', color: c.text.secondary, lineHeight: 1.45 }}>
                      {toDisplayText(item?.message, 'No validation message provided')}
                    </Typography>
                  </Box>
                ))}
              </Box>
            ) : (
              <EmptyReviewState text="Validation passed." tone="success" />
            )}
          </ReviewSection>

          <ReviewSection title="Gate warnings" tone={warnings.length > 0 ? 'warning' : 'success'}>
            {warnings.length > 0 ? (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                {warnings.map((warning, warningIndex) => {
                  const gateStatus = getGateStatus(warning);
                  const reasons = Array.isArray(warning?.reasons) ? warning.reasons : [];

                  return (
                    <Box
                      key={`warning-${warningIndex}`}
                      sx={{
                        p: 1,
                        borderRadius: `${c.radius.xs}px`,
                        border: `1px solid ${c.border.subtle}`,
                        bgcolor: c.bg.elevated,
                      }}
                    >
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.6, mb: reasons.length ? 0.75 : 0 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: c.text.primary, fontWeight: 650 }}>
                          {toDisplayText(warning?.code, 'warning')}
                        </Typography>
                        <Chip
                          label={gateStatus.label}
                          size="small"
                          sx={{
                            bgcolor: gateStatus.bg,
                            color: gateStatus.color,
                            fontSize: '0.66rem',
                            height: 20,
                            '& .MuiChip-label': { px: 0.7 },
                          }}
                        />
                      </Box>
                      {reasons.length > 0 ? (
                        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55 }}>
                          {reasons.map((reason: unknown, reasonIndex: number) => {
                            const reasonObj = reason && typeof reason === 'object' ? reason as Record<string, any> : {};
                            const reasonText = typeof reason === 'string' ? reason : toDisplayText(reasonObj.message, 'No reason message provided');

                            return (
                              <Box key={`warning-${warningIndex}-reason-${reasonIndex}`} sx={{ pl: 1, borderLeft: `2px solid ${c.border.subtle}` }}>
                                <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.5, mb: 0.2 }}>
                                  <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, fontWeight: 600 }}>
                                    {toDisplayText(reasonObj.code, 'reason')}
                                  </Typography>
                                  {reasonObj.severity != null && <MetaChip label={toDisplayText(reasonObj.severity, 'severity')} tone="warning" />}
                                </Box>
                                <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, lineHeight: 1.4 }}>
                                  {reasonText}
                                </Typography>
                              </Box>
                            );
                          })}
                        </Box>
                      ) : (
                        <EmptyReviewState text="No warning reasons provided." />
                      )}
                    </Box>
                  );
                })}
              </Box>
            ) : (
              <EmptyReviewState text="No gate warnings." tone="success" />
            )}
          </ReviewSection>

          <ReviewSection title="Evidence refs">
            {evidenceRefs.length > 0 ? (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
                {evidenceRefs.map((ref, index) => (
                  <MetaChip key={`evidence-${index}-${ref}`} label={toDisplayText(ref, 'evidence_ref')} />
                ))}
              </Box>
            ) : (
              <EmptyReviewState text="No evidence refs attached" />
            )}
          </ReviewSection>

          <ReviewSection title="Policy refs">
            {policyRefs.length > 0 ? (
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
                {policyRefs.map((ref, index) => (
                  <MetaChip key={`policy-${index}-${ref}`} label={toDisplayText(ref, 'policy_ref')} />
                ))}
              </Box>
            ) : (
              <EmptyReviewState text="No policy refs attached" />
            )}
          </ReviewSection>
        </Box>
      </Box>
    );
  };

  const CandidateRequirements: React.FC<{ candidate: SkillSpecCandidate }> = ({ candidate }) => {
    const spec = candidate.skill_spec || {};

    return (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
          flexShrink: 0,
        }}
      >
        <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700, mb: 1.5 }}>
          Requirements & declared metadata
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 1.25 }}>
          <ReviewSection title="Required tools">
            <ChipList values={spec.required_tools} empty="No required tools declared" />
          </ReviewSection>
          <ReviewSection title="Required MCP servers">
            <ChipList values={spec.required_mcp_servers} empty="No MCP servers declared" />
          </ReviewSection>
          <ReviewSection title="Compatible providers">
            <ChipList values={spec.compatible_providers} empty="No compatible providers declared" />
          </ReviewSection>
          <ReviewSection title="Tested models">
            <ChipList values={spec.tested_models} empty="No tested models declared" />
          </ReviewSection>
          <ReviewSection title="Recommended models">
            <ChipList values={spec.recommended_models} empty="No recommended models declared" />
          </ReviewSection>
          <ReviewSection title="Unsupported models">
            <ChipList values={spec.unsupported_models} empty="No unsupported models declared" tone="warning" />
          </ReviewSection>
          <ReviewSection title="Tags">
            <ChipList values={spec.tags} empty="No tags attached" />
          </ReviewSection>
          <ReviewSection title="Categories">
            <ChipList values={spec.categories} empty="No categories attached" />
          </ReviewSection>
          <Box sx={{ gridColumn: { xs: 'auto', lg: '1 / -1' } }}>
            <ReviewSection title="Declared risks" tone={asArray(spec.risks).length > 0 ? 'warning' : 'success'}>
              <ChipList values={spec.risks} empty="No risks declared" tone="warning" />
            </ReviewSection>
          </Box>
        </Box>
      </Box>
    );
  };

  const CandidateSourcePanel: React.FC<{ candidate: SkillSpecCandidate }> = ({ candidate }) => {
    const spec = candidate.skill_spec || {};
    const provenance = isPlainObject(spec.provenance) ? spec.provenance : {};
    const provenanceEntries = Object.entries(provenance);

    return (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
          flexShrink: 0,
        }}
      >
        <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700, mb: 1.5 }}>
          Source & provenance
        </Typography>
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(3, minmax(0, 1fr))' }, gap: 1.25, mb: 1.25 }}>
          <DetailRow label="Source" value={candidate.source} />
          <DetailRow label="Source ref" value={candidate.source_ref} />
          <DetailRow label="Status" value={candidate.status} tone={candidate.status === 'rejected' ? 'error' : candidate.status === 'installed' ? 'success' : 'default'} />
          <DetailRow label="Install approval" value={candidate.install_approved ? 'approved' : 'not approved'} tone={candidate.install_approved ? 'success' : 'warning'} />
          <DetailRow label="Source format" value={spec.source_format} />
          <DetailRow label="Metadata confidence" value={spec.metadata_confidence} />
        </Box>
        <ReviewSection title="Provenance metadata">
          {provenanceEntries.length > 0 ? (
            <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 0.75 }}>
              {provenanceEntries.map(([key, value]) => (
                <Box
                  key={key}
                  sx={{
                    p: 1,
                    borderRadius: `${c.radius.xs}px`,
                    border: `1px solid ${c.border.subtle}`,
                    bgcolor: c.bg.elevated,
                    minWidth: 0,
                  }}
                >
                  <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, mb: 0.35, fontWeight: 650 }}>
                    {key}
                  </Typography>
                  <Typography
                    title={toCompactValue(value)}
                    sx={{
                      fontSize: '0.74rem',
                      color: c.text.secondary,
                      fontFamily: typeof value === 'object' && value !== null ? c.font.mono : c.font.sans,
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                    }}
                  >
                    {toCompactValue(value)}
                  </Typography>
                </Box>
              ))}
            </Box>
          ) : (
            <EmptyReviewState text="No provenance metadata attached" />
          )}
        </ReviewSection>
      </Box>
    );
  };

  const contractTone = (value: unknown): 'default' | 'success' | 'warning' | 'error' => {
    const normalized = toDisplayText(value, '').toLowerCase();
    if (['always_allow', 'active', 'known', 'true'].includes(normalized)) return 'success';
    if (['ask', 'unknown', 'inactive'].includes(normalized)) return 'warning';
    if (['deny', 'blocked', 'not_found', 'false'].includes(normalized)) return 'error';
    return 'default';
  };

  const RequirementsContractPanel: React.FC<{
    contract: SkillCandidateRequirementsContract | null;
    loading: boolean;
    error: string | null;
  }> = ({ contract, loading, error }) => {
    const summary = contract?.summary ?? {};
    const toolRows = Array.isArray(contract?.tools) ? contract.tools : [];
    const mcpRows = Array.isArray(contract?.mcp_servers) ? contract.mcp_servers : [];
    const warnings = Array.isArray(contract?.warnings) ? contract.warnings : [];

    return (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
          flexShrink: 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1.5 }}>
          <Box>
            <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700 }}>
              Requirements contract
            </Typography>
            <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, mt: 0.25 }}>
              Read-only map against Actions and Modes. No permissions are changed.
            </Typography>
          </Box>
          {loading && <CircularProgress size={16} sx={{ color: c.accent.primary }} />}
        </Box>

        {error ? (
          <ReviewSection title="Contract unavailable" tone="error">
            <EmptyReviewState text={error} />
          </ReviewSection>
        ) : !contract && loading ? (
          <ReviewSection title="Loading contract">
            <EmptyReviewState text="Checking declared requirements..." />
          </ReviewSection>
        ) : !contract ? (
          <ReviewSection title="Contract unavailable">
            <EmptyReviewState text="No requirements contract loaded" />
          </ReviewSection>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 1.25 }}>
            <ReviewSection title="Summary">
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
                <MetaChip label={`tools ${summary.declared_tool_count ?? 0}`} />
                <MetaChip label={`known ${summary.known_tool_count ?? 0}`} tone="success" />
                <MetaChip label={`missing ${summary.missing_tool_count ?? 0}`} tone={(summary.missing_tool_count ?? 0) > 0 ? 'error' : 'default'} />
                <MetaChip label={`MCP ${summary.declared_mcp_count ?? 0}`} />
                <MetaChip label={`blocked ${summary.blocked_count ?? 0}`} tone={(summary.blocked_count ?? 0) > 0 ? 'error' : 'default'} />
                <MetaChip label={`unknown ${summary.unknown_count ?? 0}`} tone={(summary.unknown_count ?? 0) > 0 ? 'warning' : 'default'} />
              </Box>
            </ReviewSection>

            <ReviewSection title="Warnings" tone={warnings.length > 0 ? 'warning' : 'success'}>
              {warnings.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {warnings.map((warning, index) => (
                    <Typography key={`contract-warning-${index}`} sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.4 }}>
                      {warning}
                    </Typography>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No contract warnings." tone="success" />
              )}
            </ReviewSection>

            <ReviewSection title="Required tools">
              {toolRows.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                  {toolRows.map((tool, index) => (
                    <Box key={`contract-tool-${index}-${tool.name}`} sx={{ p: 1, borderRadius: `${c.radius.xs}px`, border: `1px solid ${c.border.subtle}`, bgcolor: c.bg.elevated }}>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.55, alignItems: 'center', mb: 0.45 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: c.text.primary, fontWeight: 650 }}>
                          {toDisplayText(tool.name, 'tool')}
                        </Typography>
                        <MetaChip label={tool.known === true ? 'known' : tool.known === false ? 'not_found' : 'unknown'} tone={contractTone(tool.known)} />
                        <MetaChip label={toDisplayText(tool.permission, 'unknown')} tone={contractTone(tool.permission)} />
                        <MetaChip label={toDisplayText(tool.source, 'unknown')} />
                      </Box>
                      {asArray(tool.notes).slice(0, 2).map((note, noteIndex) => (
                        <Typography key={`contract-tool-note-${index}-${noteIndex}`} sx={{ fontSize: '0.7rem', color: c.text.ghost, lineHeight: 1.35 }}>
                          {toDisplayText(note)}
                        </Typography>
                      ))}
                    </Box>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No required tools declared" />
              )}
            </ReviewSection>

            <ReviewSection title="Required MCP servers">
              {mcpRows.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
                  {mcpRows.map((server, index) => (
                    <Box key={`contract-mcp-${index}-${server.name}`} sx={{ p: 1, borderRadius: `${c.radius.xs}px`, border: `1px solid ${c.border.subtle}`, bgcolor: c.bg.elevated }}>
                      <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.55, alignItems: 'center', mb: 0.45 }}>
                        <Typography sx={{ fontSize: '0.76rem', color: c.text.primary, fontWeight: 650 }}>
                          {toDisplayText(server.name, 'mcp_server')}
                        </Typography>
                        <MetaChip label={server.known === true ? 'known' : server.known === false ? 'not_found' : 'unknown'} tone={contractTone(server.known)} />
                        <MetaChip label={toDisplayText(server.activation_state, 'unknown')} tone={contractTone(server.activation_state)} />
                      </Box>
                      {asArray(server.notes).slice(0, 2).map((note, noteIndex) => (
                        <Typography key={`contract-mcp-note-${index}-${noteIndex}`} sx={{ fontSize: '0.7rem', color: c.text.ghost, lineHeight: 1.35 }}>
                          {toDisplayText(note)}
                        </Typography>
                      ))}
                    </Box>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No required MCP servers declared" />
              )}
            </ReviewSection>
          </Box>
        )}
      </Box>
    );
  };

  const qualityTone = (value: unknown): 'default' | 'success' | 'warning' | 'error' => {
    const normalized = toDisplayText(value, '').toLowerCase();
    if (['strong', 'clear', 'not_required', 'true', 'low'].includes(normalized)) return 'success';
    if (['needs_improvement', 'missing', 'web_research_recommended', 'medium', 'false'].includes(normalized)) return 'warning';
    if (['high', 'requirements_declared_boundary_missing', 'blocked', 'error'].includes(normalized)) return 'error';
    return 'default';
  };

  const SkillQualityReviewPanel: React.FC<{
    review: SkillCandidateQualityReview | null;
    loading: boolean;
    error: string | null;
  }> = ({ review, loading, error }) => {
    const improvementItems = Array.isArray(review?.improvement_items) ? review.improvement_items : [];
    const recommendedSections = Array.isArray(review?.recommended_sections) ? review.recommended_sections : [];
    const missingSections = Array.isArray(review?.missing_sections) ? review.missing_sections : [];
    const riskNotes = Array.isArray(review?.risk_notes) ? review.risk_notes : [];
    const qualityContract = isPlainObject(review?.quality_contract) ? review?.quality_contract : {};
    const contractChecks = [
      ['Expert role', qualityContract.has_role_definition],
      ['Methodology', qualityContract.has_expert_methodology],
      ['Decision criteria', qualityContract.has_decision_criteria],
      ['Validation', qualityContract.has_validation_guidance],
      ['Pitfalls', qualityContract.has_pitfalls],
      ['Boundaries', qualityContract.has_operational_boundaries],
      ['Skill / Action boundary', qualityContract.has_action_boundary_statement],
    ];
    const contractWarnings = Array.isArray(qualityContract.warnings) ? qualityContract.warnings : [];
    const research = isPlainObject(review?.research_recommendation) ? review?.research_recommendation : null;
    const safeToAutoApply = review?.safe_to_auto_apply === true;
    const humanStrengths = Array.isArray(review?.human_strengths) ? review.human_strengths : [];
    const humanMissingItems = Array.isArray(review?.human_missing_items) ? review.human_missing_items : [];
    const humanNextSteps = Array.isArray(review?.human_next_steps) ? review.human_next_steps : [];
    const humanSummary = toDisplayText(review?.human_summary, toDisplayText(review?.improvement_summary, 'No summary provided.'));
    const boundaryLabel = review?.action_boundary_status === 'clear'
      ? 'Skill/Action boundary is clear'
      : 'Skill/Action boundary needs clarification';
    const itemTitle = (item: Record<string, unknown>) => {
      const code = toDisplayText(item.code, '');
      if (typeof item.title === 'string' && item.title.trim()) return item.title;
      if (code === 'clarify_skill_not_action' || code === 'missing_action_boundary_statement') {
        return 'Clarify that this skill does not activate tools or permissions';
      }
      if (code === 'add_expert_role') return 'Define the expert role';
      if (code === 'add_methodology') return 'Explain the expert methodology';
      if (code === 'add_validation_guidance') return 'Add validation criteria';
      return toDisplayText(item.title, toDisplayText(item.code, 'Improvement'));
    };

    return (
      <Box
        sx={{
          mb: 2,
          p: 2,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
          flexShrink: 0,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1.5 }}>
          <Box>
            <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700 }}>
              Skill quality review
            </Typography>
            <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, mt: 0.25 }}>
              Read-only expert-skill checklist. No apply, diff, install, approval, or mutation.
            </Typography>
          </Box>
          {loading && <CircularProgress size={16} sx={{ color: c.accent.primary }} />}
        </Box>

        {error ? (
          <ReviewSection title="Review unavailable" tone="error">
            <EmptyReviewState text={error} />
          </ReviewSection>
        ) : !review && loading ? (
          <ReviewSection title="Loading review">
            <EmptyReviewState text="Checking expert-skill structure..." />
          </ReviewSection>
        ) : !review ? (
          <ReviewSection title="Review unavailable">
            <EmptyReviewState text="No quality review loaded" />
          </ReviewSection>
        ) : (
          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 1.25 }}>
            <ReviewSection title="Summary" tone={qualityTone(review.status)}>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary, lineHeight: 1.5, mb: 1 }}>
                {humanSummary}
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
                <MetaChip label={toDisplayText(review.human_status_label, toDisplayText(review.status, 'unknown status'))} tone={qualityTone(review.status)} />
                <MetaChip
                  label={safeToAutoApply ? 'Automatic changes available' : 'Review only · No automatic changes'}
                  tone={safeToAutoApply ? 'success' : 'warning'}
                />
                <MetaChip
                  label={boundaryLabel}
                  tone={qualityTone(review.action_boundary_status)}
                />
              </Box>
            </ReviewSection>

            <ReviewSection title="What is already strong" tone={humanStrengths.length > 0 ? 'success' : 'default'}>
              {humanStrengths.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {humanStrengths.map((strength, index) => (
                    <Typography key={`quality-strength-${index}`} sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.4 }}>
                      {toDisplayText(strength)}
                    </Typography>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No strengths detected yet." />
              )}
            </ReviewSection>

            <ReviewSection title="What still needs work" tone={humanMissingItems.length > 0 ? 'warning' : 'success'}>
              <ChipList values={humanMissingItems} empty="No missing expert-skill items detected" tone="warning" />
            </ReviewSection>

            <ReviewSection title="Suggested next steps" tone={humanNextSteps.length > 0 ? 'warning' : 'success'}>
              {humanNextSteps.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {humanNextSteps.map((step, index) => (
                    <Typography key={`quality-next-step-${index}`} sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.4 }}>
                      {toDisplayText(step)}
                    </Typography>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No next steps suggested." tone="success" />
              )}
            </ReviewSection>

            <ReviewSection title="Research recommendation" tone={qualityTone(research?.status)}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65, mb: 0.75 }}>
                <MetaChip label={toDisplayText(research?.status, 'not provided')} tone={qualityTone(research?.status)} />
              </Box>
              <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.45 }}>
                {toDisplayText(research?.message, 'No research recommendation provided.')}
              </Typography>
            </ReviewSection>

            <Box sx={{ gridColumn: { xs: 'auto', lg: '1 / -1' } }}>
              <ReviewSection title={toDisplayText(review.technical_details_label, 'Technical reviewer details')} tone={improvementItems.length > 0 ? 'warning' : 'success'}>
                {improvementItems.length > 0 ? (
                  <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 0.85 }}>
                    {improvementItems.map((rawItem, index) => {
                      const item = isPlainObject(rawItem) ? rawItem : {};
                      const title = itemTitle(item);
                      const severity = toDisplayText(item.severity, 'unknown');

                      return (
                        <Box
                          key={`quality-item-${index}-${toCompactValue(item.code)}`}
                          sx={{
                            p: 1,
                            borderRadius: `${c.radius.xs}px`,
                            border: `1px solid ${c.border.subtle}`,
                            bgcolor: c.bg.elevated,
                          }}
                        >
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 0.55, mb: 0.55 }}>
                            <Typography sx={{ fontSize: '0.76rem', color: c.text.primary, fontWeight: 650 }}>
                              {title}
                            </Typography>
                            <MetaChip label={severity} tone={qualityTone(severity)} />
                            <MetaChip label={`technical code: ${toDisplayText(item.code, 'no_code')}`} />
                            <MetaChip
                              label={item.auto_apply_supported === true ? 'auto apply supported' : 'review only'}
                              tone={item.auto_apply_supported === true ? 'success' : 'warning'}
                            />
                          </Box>
                          <Typography sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.45, mb: 0.65 }}>
                            {toDisplayText(item.message, 'No improvement message provided.')}
                          </Typography>
                          <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 0.65 }}>
                            <Box>
                              <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, mb: 0.2, fontWeight: 600 }}>
                                Suggested section
                              </Typography>
                              <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, lineHeight: 1.35 }}>
                                {toDisplayText(item.suggested_section, '—')}
                              </Typography>
                            </Box>
                            <Box>
                              <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, mb: 0.2, fontWeight: 600 }}>
                                Reason
                              </Typography>
                              <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, lineHeight: 1.35 }}>
                                {toDisplayText(item.reason, '—')}
                              </Typography>
                            </Box>
                          </Box>
                        </Box>
                      );
                    })}
                  </Box>
                ) : (
                  <EmptyReviewState text="No improvements suggested." tone="success" />
                )}
              </ReviewSection>
            </Box>

            <ReviewSection title="Recommended sections">
              <ChipList values={recommendedSections} empty="No recommended sections provided" />
            </ReviewSection>

            <ReviewSection title="Missing sections" tone={missingSections.length > 0 ? 'warning' : 'success'}>
              <ChipList values={missingSections} empty="No missing sections detected" tone="warning" />
            </ReviewSection>

            <ReviewSection title="Quality contract checks">
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65 }}>
                {contractChecks.map(([label, present]) => (
                  <MetaChip
                    key={`quality-contract-${label}`}
                    label={`${label}: ${present === true ? 'present' : present === false ? 'missing' : 'unknown'}`}
                    tone={present === true ? 'success' : present === false ? 'warning' : 'default'}
                  />
                ))}
              </Box>
            </ReviewSection>

            <ReviewSection title="Risk notes" tone={riskNotes.length > 0 ? 'warning' : 'success'}>
              {riskNotes.length > 0 ? (
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.5 }}>
                  {riskNotes.map((note, index) => (
                    <Typography key={`quality-risk-${index}`} sx={{ fontSize: '0.74rem', color: c.text.secondary, lineHeight: 1.4 }}>
                      {toDisplayText(note)}
                    </Typography>
                  ))}
                </Box>
              ) : (
                <EmptyReviewState text="No risk notes provided." tone="success" />
              )}
            </ReviewSection>

            {contractWarnings.length > 0 && (
              <Box sx={{ gridColumn: { xs: 'auto', lg: '1 / -1' } }}>
                <ReviewSection title="Contract warnings" tone="warning">
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.65 }}>
                    {contractWarnings.map((warning, index) => {
                      const warningObj = isPlainObject(warning) ? warning : {};
                      return (
                        <Box key={`quality-contract-warning-${index}`} sx={{ pl: 1, borderLeft: `2px solid ${c.border.subtle}` }}>
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, alignItems: 'center', mb: 0.2 }}>
                            <Typography sx={{ fontSize: '0.72rem', color: c.text.secondary, fontWeight: 600 }}>
                              {toDisplayText(warningObj.code, 'warning')}
                            </Typography>
                            <MetaChip label={toDisplayText(warningObj.severity, 'severity')} tone={qualityTone(warningObj.severity)} />
                          </Box>
                          <Typography sx={{ fontSize: '0.72rem', color: c.text.ghost, lineHeight: 1.4 }}>
                            {toDisplayText(warningObj.message, toDisplayText(warning))}
                          </Typography>
                        </Box>
                      );
                    })}
                  </Box>
                </ReviewSection>
              </Box>
            )}
          </Box>
        )}
      </Box>
    );
  };

  const ImportSkillPanel: React.FC = () => {
    const policy = skillImportPreview?.policy || {};
    const preview = skillImportPreview?.preview || {};
    const detection = skillImportPreview?.detection || {};
    const riskReport = (preview.risk_report && typeof preview.risk_report === 'object') ? preview.risk_report as Record<string, any> : {};
    const compatibility = (preview.compatibility_score && typeof preview.compatibility_score === 'object') ? preview.compatibility_score as Record<string, any> : {};
    const compatibilityComponents = (compatibility.components && typeof compatibility.components === 'object') ? compatibility.components as Record<string, any> : {};
    const migration = (preview.migration_assistant && typeof preview.migration_assistant === 'object') ? preview.migration_assistant as Record<string, any> : {};
    const migrationSuggestions = Array.isArray(migration.suggestions) ? migration.suggestions : [];
    const specPreview = (preview.skill_spec_preview && typeof preview.skill_spec_preview === 'object') ? preview.skill_spec_preview as Record<string, any> : {};
    const importContract = (preview.import_contract && typeof preview.import_contract === 'object') ? preview.import_contract as Record<string, any> : {};
    const provenance = (specPreview.provenance && typeof specPreview.provenance === 'object') ? specPreview.provenance as Record<string, any> : {};
    const warnings = Array.isArray(riskReport.warnings) ? riskReport.warnings : [];
    const risks = Array.isArray(riskReport.risks) ? riskReport.risks : [];
    const policyReasons = Array.isArray(policy.reasons) ? policy.reasons : [];
    const requiredTools = Array.isArray(preview.required_tools) ? preview.required_tools : [];
    const requiredMcpServers = Array.isArray(preview.required_mcp_servers) ? preview.required_mcp_servers : [];
    const previewDiff = typeof preview.preview_diff === 'string' ? preview.preview_diff : '';
    const canCreate = skillImportPreview?.can_create_candidate === true;
    const formatOptions = [
      'markdown_prompt_pack',
      'claude_skill',
      'anthropic_skill',
      'openswarm_skillspec',
      'openswarm_legacy_skill',
      'cursor_rule',
      'windsurf_rule',
      'copilot_instruction',
      'codex_instruction',
      'gemini_cli_config',
      'qwen_code_config',
      'kiro_spec',
      'mcp_tool_instruction',
      'skill_pack',
      'repo',
      'zip',
      'folder',
      'unknown',
    ];

    return (
      <Box
        sx={{
          mb: 1.5,
          p: 1.25,
          borderRadius: `${c.radius.md}px`,
          border: `1px solid ${c.border.subtle}`,
          bgcolor: c.bg.secondary,
          boxShadow: c.shadow.sm,
        }}
      >
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 1, mb: 1 }}>
          <Box sx={{ minWidth: 0 }}>
            <Typography sx={{ fontSize: '0.8rem', color: c.text.primary, fontWeight: 700 }}>
              Import Skill
            </Typography>
            <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, mt: 0.2, lineHeight: 1.35 }}>
              Preview only. No install, execution, tools or MCP activation.
            </Typography>
          </Box>
          {(skillImportPreviewLoading || skillImportCandidateCreateLoading) && <CircularProgress size={16} sx={{ color: c.accent.primary }} />}
        </Box>

        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.75 }}>
          <TextField
            select
            SelectProps={{ native: true }}
            size="small"
            label="Format"
            value={importSourceFormat}
            onChange={(event) => setImportSourceFormat(event.target.value)}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.78rem' } }}
          >
            {formatOptions.map((option) => (
              <option key={option} value={option}>{option}</option>
            ))}
          </TextField>
          <TextField
            size="small"
            label="Name"
            value={importName}
            onChange={(event) => setImportName(event.target.value)}
            placeholder="Imported Skill"
            sx={{ '& .MuiInputBase-input': { fontSize: '0.78rem' } }}
          />
          <Box sx={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 0.75 }}>
            <TextField
              size="small"
              label="Author"
              value={importAuthor}
              onChange={(event) => setImportAuthor(event.target.value)}
              sx={{ '& .MuiInputBase-input': { fontSize: '0.78rem' } }}
            />
            <TextField
              size="small"
              label="License"
              value={importLicense}
              onChange={(event) => setImportLicense(event.target.value)}
              sx={{ '& .MuiInputBase-input': { fontSize: '0.78rem' } }}
            />
          </Box>
          <TextField
            size="small"
            label="Source ref"
            value={importSourceUrl}
            onChange={(event) => setImportSourceUrl(event.target.value)}
            placeholder="file://prepared/SKILL.md"
            sx={{ '& .MuiInputBase-input': { fontSize: '0.78rem' } }}
          />
          <TextField
            multiline
            minRows={5}
            maxRows={10}
            label="Skill material"
            value={importContent}
            onChange={(event) => setImportContent(event.target.value)}
            placeholder={'# Skill name\nInstructions to preview...'}
            sx={{ '& .MuiInputBase-input': { fontSize: '0.76rem', fontFamily: c.font.mono } }}
          />

          <Box sx={{ display: 'flex', gap: 0.75, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
            <Button
              size="small"
              variant="outlined"
              disabled={!importContent.trim() || skillImportPreviewLoading}
              onClick={handlePreviewImport}
              sx={{ textTransform: 'none', borderRadius: `${c.radius.sm}px`, fontSize: '0.76rem' }}
            >
              Preview import
            </Button>
            <Tooltip title={canCreate ? 'Create a reviewable candidate. This does not install.' : 'Preview must pass policy before candidate creation.'}>
              <span>
                <Button
                  size="small"
                  variant="contained"
                  disabled={!canCreate || skillImportCandidateCreateLoading}
                  onClick={handleCreateImportCandidate}
                  sx={{ textTransform: 'none', borderRadius: `${c.radius.sm}px`, fontSize: '0.76rem', boxShadow: 'none' }}
                >
                  Create candidate
                </Button>
              </span>
            </Tooltip>
          </Box>

          {(skillImportPreviewError || skillImportCandidateCreateError) && (
            <Alert severity="error" sx={{ borderRadius: `${c.radius.sm}px` }}>
              {skillImportPreviewError || skillImportCandidateCreateError}
            </Alert>
          )}

          {skillImportPreview && (
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.65, pt: 0.5 }}>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                <MetaChip label={`detected ${toDisplayText(detection.detected_format, 'unknown')}`} />
                <MetaChip label={`policy ${toDisplayText(policy.decision, 'unknown')}`} tone={canCreate ? 'success' : policy.decision === 'blocked' ? 'error' : 'warning'} />
                <MetaChip label={`compat ${toDisplayText(compatibility.status, 'unmeasured')}`} tone={compatibility.status === 'blocked' ? 'error' : compatibility.status === 'compatible_preview' ? 'success' : 'warning'} />
                <MetaChip label={`migration ${toDisplayText(migration.status, 'not available')}`} tone={migration.status === 'blocked' ? 'error' : migration.status === 'ready_for_candidate_review' ? 'success' : 'warning'} />
                <MetaChip label="preview only" tone="success" />
                <MetaChip label="install disabled" tone="warning" />
                <MetaChip label="execution disabled" tone="warning" />
                <MetaChip label="tools/MCP disabled" tone="warning" />
              </Box>
              <Typography sx={{ fontSize: '0.7rem', color: c.text.secondary, lineHeight: 1.4 }}>
                Preview id: {toDisplayText(preview.preview_id, 'not available')}
              </Typography>

              <ReviewSection title="Compatibility" tone={compatibility.status === 'blocked' ? 'error' : compatibility.status === 'compatible_preview' ? 'success' : 'warning'}>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.85 }}>
                  <MetaChip label={`score ${toDisplayText(compatibility.score, 'unmeasured')}`} />
                  <MetaChip label={`status ${toDisplayText(compatibility.status, 'unmeasured')}`} />
                  <MetaChip label={`confidence ${toDisplayText(compatibility.confidence, 'unmeasured')}`} />
                  <MetaChip label="install disabled" tone="warning" />
                  <MetaChip label="execution disabled" tone="warning" />
                  <MetaChip label="tools/MCP disabled" tone="warning" />
                </Box>
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', lg: '1fr 1fr' }, gap: 0.65 }}>
                  {Object.entries(compatibilityComponents).map(([key, raw]) => {
                    const component = isPlainObject(raw) ? raw : {};
                    const status = toDisplayText(component.status, 'unmeasured');
                    const reasons = asArray(component.reasons).slice(0, 2);
                    return (
                      <Box key={`compat-${key}`} sx={{ p: 0.75, borderRadius: `${c.radius.sm}px`, border: `1px solid ${c.border.subtle}`, bgcolor: c.bg.secondary }}>
                        <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center', mb: 0.35 }}>
                          <Typography sx={{ fontSize: '0.69rem', color: c.text.secondary, fontWeight: 700 }}>{toDisplayText(key)}</Typography>
                          <MetaChip label={toDisplayText(component.score, 'unmeasured')} tone={status === 'blocked' ? 'error' : status === 'compatible_preview' ? 'success' : 'warning'} />
                        </Box>
                        {reasons.map((reason, index) => (
                          <Typography key={`compat-${key}-reason-${index}`} sx={{ fontSize: '0.66rem', color: c.text.ghost, lineHeight: 1.35 }}>
                            {toDisplayText(reason)}
                          </Typography>
                        ))}
                      </Box>
                    );
                  })}
                </Box>
                {asArray(compatibility.notes).length > 0 && (
                  <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, lineHeight: 1.4, mt: 0.75 }}>
                    Notes: {asArray(compatibility.notes).slice(0, 4).map((item) => toDisplayText(item)).join(' · ')}
                  </Typography>
                )}
              </ReviewSection>

              <ReviewSection title="Migration Assistant" tone={migration.status === 'blocked' ? 'error' : migration.status === 'ready_for_candidate_review' ? 'success' : 'warning'}>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
                  <MetaChip label={`status ${toDisplayText(migration.status, 'not available')}`} />
                  <MetaChip label={`suggestions ${toDisplayText(migration.suggestion_count, 0)}`} />
                  <MetaChip label="auto apply disabled" tone="warning" />
                </Box>
                {migrationSuggestions.length > 0 ? (
                  <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.55 }}>
                    {migrationSuggestions.slice(0, 8).map((suggestion, index) => {
                      const item = isPlainObject(suggestion) ? suggestion : {};
                      return (
                        <Box key={`migration-${index}`} sx={{ pl: 0.75, borderLeft: `2px solid ${item.severity === 'critical' ? c.status.error : c.border.subtle}` }}>
                          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.45, alignItems: 'center' }}>
                            <Typography sx={{ fontSize: '0.7rem', color: c.text.secondary, fontWeight: 700 }}>{toDisplayText(item.title, item.code || 'suggestion')}</Typography>
                            <MetaChip label={toDisplayText(item.severity, 'medium')} tone={item.severity === 'critical' ? 'error' : item.severity === 'high' ? 'warning' : 'default'} />
                            <MetaChip label={toDisplayText(item.target, 'target')} />
                          </Box>
                          <Typography sx={{ fontSize: '0.67rem', color: c.text.ghost, lineHeight: 1.35, mt: 0.2 }}>{toDisplayText(item.message)}</Typography>
                        </Box>
                      );
                    })}
                  </Box>
                ) : (
                  <EmptyReviewState text="No migration suggestions reported." tone="success" />
                )}
              </ReviewSection>

              <ReviewSection title="Risk / Policy" tone={policy.decision === 'blocked' || risks.length > 0 ? 'error' : canCreate ? 'success' : 'warning'}>
                <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5, mb: 0.75 }}>
                  <MetaChip label={`decision ${toDisplayText(policy.decision, 'unknown')}`} tone={policy.decision === 'blocked' ? 'error' : canCreate ? 'success' : 'warning'} />
                  <MetaChip label={`risk ${toDisplayText(policy.risk_level, 'unknown')}`} />
                  <MetaChip label={`tools ${requiredTools.length}`} tone={requiredTools.length ? 'warning' : 'success'} />
                  <MetaChip label={`mcp ${requiredMcpServers.length}`} tone={requiredMcpServers.length ? 'warning' : 'success'} />
                  <MetaChip label="no activation" tone="success" />
                </Box>
                {policyReasons.length > 0 && (
                  <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, lineHeight: 1.4 }}>
                    Blocked/review reasons: {policyReasons.map((item) => toDisplayText(isPlainObject(item) ? item.code : item)).join(', ')}
                  </Typography>
                )}
                {risks.length > 0 && (
                  <Typography sx={{ fontSize: '0.68rem', color: c.status.error, lineHeight: 1.4, mt: 0.35 }}>
                    Risks: {risks.map((item) => toDisplayText(item)).join(', ')}
                  </Typography>
                )}
                {warnings.length > 0 && (
                  <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, lineHeight: 1.4, mt: 0.35 }}>
                    Warnings: {warnings.slice(0, 4).map((item) => toDisplayText(item)).join(', ')}
                  </Typography>
                )}
              </ReviewSection>

              <ReviewSection title="Provenance">
                <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr 1fr', lg: 'repeat(3, minmax(0, 1fr))' }, gap: 0.7 }}>
                  <DetailRow label="Source format" value={preview.source_format || importContract.source_format || specPreview.source_format} />
                  <DetailRow label="Detected format" value={detection.detected_format} />
                  <DetailRow label="Import adapter" value={preview.import_adapter || importContract.import_adapter || provenance.import_adapter} />
                  <DetailRow label="Author" value={importContract.source_author || provenance.source_author} />
                  <DetailRow label="License" value={importContract.source_license || provenance.source_license} />
                  <DetailRow label="Source ref" value={importContract.source_url || provenance.source_url} />
                  <DetailRow label="Source hash" value={importContract.source_hash || provenance.source_hash} />
                  <DetailRow label="Metadata confidence" value={importContract.metadata_confidence || specPreview.metadata_confidence} />
                </Box>
              </ReviewSection>

              {previewDiff && (
                <ReviewSection title="Preview diff">
                  <Button size="small" onClick={() => setImportDiffOpen((prev) => !prev)} sx={{ textTransform: 'none', fontSize: '0.72rem', p: 0, minWidth: 0 }}>
                    {importDiffOpen ? 'Hide preview diff' : 'Show preview diff'}
                  </Button>
                  <Collapse in={importDiffOpen}>
                    <Box component="pre" sx={{ mt: 0.75, p: 1, borderRadius: `${c.radius.sm}px`, bgcolor: c.bg.secondary, color: c.text.secondary, fontSize: '0.66rem', overflow: 'auto', maxHeight: 180, whiteSpace: 'pre-wrap', fontFamily: c.font.mono }}>
                      {previewDiff}
                    </Box>
                  </Collapse>
                  <Typography sx={{ fontSize: '0.66rem', color: c.text.ghost, mt: 0.6 }}>
                    Preview diff is read-only; edit the source material and preview again.
                  </Typography>
                </ReviewSection>
              )}

              <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, lineHeight: 1.4 }}>
                Candidate creation only creates a review candidate. Install remains separate in candidate review.
              </Typography>
            </Box>
          )}
        </Box>
      </Box>
    );
  };

  const CandidateSidebarRow: React.FC<{ candidate: SkillSpecCandidate }> = ({ candidate }) => {
    const selected = isSelected('candidate', candidate.candidate_id);

    return (
      <Box
        onClick={() => selectCandidate(candidate.candidate_id)}
        sx={{
          display: 'flex',
          alignItems: 'flex-start',
          gap: 1,
          px: 1.5,
          py: 0.75,
          borderRadius: `${c.radius.sm}px`,
          cursor: 'pointer',
          bgcolor: selected ? c.bg.secondary : 'transparent',
          transition: 'background 0.12s',
          '&:hover': { bgcolor: selected ? c.bg.secondary : 'rgba(0,0,0,0.03)' },
        }}
      >
        <AutoFixHighIcon sx={{ fontSize: 15, color: c.accent.primary, flexShrink: 0, mt: 0.2 }} />
        <Box sx={{ minWidth: 0, flex: 1 }}>
          <Typography
            sx={{
              fontSize: '0.82rem',
              color: selected ? c.text.primary : c.text.secondary,
              fontWeight: selected ? 600 : 400,
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {candidate.skill_spec?.name || 'Untitled Skill Candidate'}
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.45, mt: 0.45 }}>
            <Chip
              label={candidate.status || 'candidate'}
              size="small"
              sx={{ bgcolor: c.bg.page, color: c.text.ghost, fontSize: '0.62rem', height: 18, '& .MuiChip-label': { px: 0.55 } }}
            />
            {candidate.install_approved && (
              <Chip
                label="approved"
                size="small"
                sx={{ bgcolor: c.status.successBg, color: c.status.success, fontSize: '0.62rem', height: 18, '& .MuiChip-label': { px: 0.55 } }}
              />
            )}
          </Box>
        </Box>
      </Box>
    );
  };

  return (
    <Box sx={{ display: 'flex', height: '100%', overflow: 'hidden', bgcolor: c.bg.page, position: 'relative' }}>
      {/* ─── Left Sidebar ─── */}
      <Box
        sx={{
          width: SIDEBAR_W, minWidth: SIDEBAR_W, height: '100%', display: 'flex', flexDirection: 'column',
          borderRight: `${c.border.width} solid ${c.border.subtle}`, bgcolor: 'transparent',
        }}
      >
        {/* Sidebar header */}
        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', px: 2, pt: 2, pb: 1 }}>
          <Typography sx={{ fontSize: '0.92rem', fontWeight: 700, color: c.text.primary }}>Skills</Typography>
          <Box sx={{ display: 'flex', gap: 0.25 }}>
            <Tooltip title="Search">
              <IconButton
                size="small"
                onClick={() => setSearchFilter((p) => (p === '' ? ' ' : ''))}
                sx={{ color: c.text.tertiary, '&:hover': { color: c.text.primary } }}
              >
                <SearchIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
            <Tooltip title="Create skill">
              <IconButton size="small" onClick={openCreate} sx={{ color: c.text.tertiary, '&:hover': { color: c.text.primary } }}>
                <AddIcon sx={{ fontSize: 18 }} />
              </IconButton>
            </Tooltip>
          </Box>
        </Box>
        <Box sx={{ px: 1.5, pb: 0.5 }}>
          <Button
            size="small"
            startIcon={<AutoFixHighIcon sx={{ fontSize: 14 }} />}
            onClick={() => setBuilderOpen(true)}
            fullWidth
            sx={{
              textTransform: 'none',
              fontSize: '0.76rem',
              fontWeight: 500,
              color: c.accent.primary,
              justifyContent: 'flex-start',
              py: 0.5,
              px: 1,
              borderRadius: `${c.radius.sm}px`,
              border: `1px dashed ${c.accent.primary}40`,
              '&:hover': { bgcolor: `${c.accent.primary}08`, borderColor: c.accent.primary },
            }}
          >
            Build with AI
          </Button>
        </Box>

        {/* Search input (toggled) */}
        <Collapse in={searchFilter !== ''}>
          <Box sx={{ px: 1.5, pb: 1 }}>
            <TextField
              placeholder="Filter skills..."
              value={searchFilter.trim()}
              onChange={(e) => setSearchFilter(e.target.value)}
              fullWidth
              size="small"
              autoFocus
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <SearchIcon sx={{ fontSize: 16, color: c.text.ghost }} />
                  </InputAdornment>
                ),
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  bgcolor: c.bg.surface, borderRadius: `${c.radius.sm}px`, fontSize: '0.82rem',
                  '& fieldset': { borderColor: c.border.medium },
                },
              }}
            />
          </Box>
        </Collapse>

        {/* Scrollable tree */}
        <Box
          sx={{
            flex: 1, overflow: 'auto', px: 0.75, pb: 2,
            '&::-webkit-scrollbar': { width: 4 },
            '&::-webkit-scrollbar-thumb': { background: c.border.medium, borderRadius: 2 },
          }}
        >
          <ImportSkillPanel />

          {/* My Skills (local) */}
          {filteredLocal.length > 0 && (
            <Box sx={{ mb: 1 }}>
              <Box
                onClick={() => toggleCategory('__local')}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.5,
                  cursor: 'pointer', userSelect: 'none',
                  '&:hover': { bgcolor: 'rgba(0,0,0,0.02)' }, borderRadius: `${c.radius.sm}px`,
                }}
              >
                {collapsedCats['__local']
                  ? <KeyboardArrowRightIcon sx={{ fontSize: 16, color: c.text.ghost }} />
                  : <KeyboardArrowDownIcon sx={{ fontSize: 16, color: c.text.ghost }} />}
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: c.text.tertiary, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  My Skills
                </Typography>
                <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, ml: 0.5 }}>({filteredLocal.length})</Typography>
              </Box>
              <Collapse in={!collapsedCats['__local']}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, mt: 0.25 }}>
                  {filteredLocal.map((sk) => (
                    <SidebarRow
                      key={sk.id}
                      label={sk.name}
                      selected={isSelected('local', sk.id)}
                      onClick={() => selectLocal(sk.id)}
                      icon={<FolderIcon sx={{ fontSize: 15, color: c.text.tertiary, flexShrink: 0 }} />}
                    />
                  ))}
                </Box>
              </Collapse>
            </Box>
          )}

          {/* Skill candidates */}
          {filteredCandidates.length > 0 && (
            <Box sx={{ mb: 1 }}>
              <Box
                onClick={() => toggleCategory('__candidates')}
                sx={{
                  display: 'flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.5,
                  cursor: 'pointer', userSelect: 'none',
                  '&:hover': { bgcolor: 'rgba(0,0,0,0.02)' }, borderRadius: `${c.radius.sm}px`,
                }}
              >
                {collapsedCats['__candidates']
                  ? <KeyboardArrowRightIcon sx={{ fontSize: 16, color: c.text.ghost }} />
                  : <KeyboardArrowDownIcon sx={{ fontSize: 16, color: c.text.ghost }} />}
                <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: c.text.tertiary, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                  Skill Candidates
                </Typography>
                <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, ml: 0.5 }}>
                  ({filteredCandidates.length}{filteredCandidates.length !== skillCandidates.length ? `/${skillCandidates.length}` : ''})
                </Typography>
              </Box>
              <Collapse in={!collapsedCats['__candidates']}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, mt: 0.25 }}>
                  {filteredCandidates.map((candidate) => (
                    <CandidateSidebarRow key={candidate.candidate_id} candidate={candidate} />
                  ))}
                </Box>
              </Collapse>
            </Box>
          )}

          {/* Registry categories */}
          {(loading || regLoading) && regSkills.length === 0 && localSkills.length === 0 ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 6 }}>
              <CircularProgress size={22} sx={{ color: c.accent.primary }} />
            </Box>
          ) : (
            categoryOrder.map((cat) => {
              const group = regGrouped[cat];
              if (!group || group.length === 0) return null;
              const isCollapsed = !!collapsedCats[cat];
              return (
                <Box key={cat} sx={{ mb: 0.5 }}>
                  <Box
                    onClick={() => toggleCategory(cat)}
                    sx={{
                      display: 'flex', alignItems: 'center', gap: 0.5, px: 1, py: 0.5,
                      cursor: 'pointer', userSelect: 'none',
                      '&:hover': { bgcolor: 'rgba(0,0,0,0.02)' }, borderRadius: `${c.radius.sm}px`,
                    }}
                  >
                    {isCollapsed
                      ? <KeyboardArrowRightIcon sx={{ fontSize: 16, color: c.text.ghost }} />
                      : <KeyboardArrowDownIcon sx={{ fontSize: 16, color: c.text.ghost }} />}
                    <Typography sx={{ fontSize: '0.72rem', fontWeight: 600, color: c.text.tertiary, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
                      {cat}
                    </Typography>
                    <Typography sx={{ fontSize: '0.68rem', color: c.text.ghost, ml: 0.5 }}>({group.length})</Typography>
                  </Box>
                  <Collapse in={!isCollapsed}>
                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.25, mt: 0.25 }}>
                      {group.map((sk) => (
                        <SidebarRow
                          key={sk.name}
                          label={sk.name}
                          selected={isSelected('registry', sk.name)}
                          onClick={() => selectRegistry(sk.name)}
                        />
                      ))}
                    </Box>
                  </Collapse>
                </Box>
              );
            })
          )}
        </Box>
      </Box>

      {/* ─── Right Detail Panel ─── */}
      <Box sx={{ flex: 1, height: '100%', display: 'flex', flexDirection: 'column', overflow: 'hidden', bgcolor: 'transparent' }}>
        {selection?.type === 'builder-preview' && builderPreview ? (
          <Box sx={{ p: 4, pb: 3, maxWidth: 1100, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5, flexShrink: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Typography sx={{ fontSize: '1.4rem', fontWeight: 700, color: c.text.primary, fontFamily: c.font.sans }}>
                  {builderPreview.name || 'Untitled Skill'}
                </Typography>
                <Chip
                  label="AI Preview"
                  size="small"
                  sx={{
                    bgcolor: `${c.accent.primary}15`,
                    color: c.accent.primary,
                    fontWeight: 600,
                    fontSize: '0.68rem',
                    height: 22,
                  }}
                />
              </Box>
            </Box>

            {builderPreview.command && (
              <Box sx={{ mb: 1.5, flexShrink: 0 }}>
                <Chip
                  icon={<TerminalIcon sx={{ fontSize: 14 }} />}
                  label={`/${builderPreview.command}`}
                  size="small"
                  sx={{
                    bgcolor: 'rgba(174,86,48,0.08)', color: c.accent.primary,
                    fontWeight: 500, fontSize: '0.78rem', height: 26,
                  }}
                />
              </Box>
            )}

            <Box sx={{ mb: 1, flexShrink: 0 }}>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost }}>
                Generated by <strong style={{ color: c.accent.primary, fontWeight: 600 }}>Skill Builder</strong>
              </Typography>
            </Box>

            {builderPreview.description && (
              <Box sx={{ mb: 2, flexShrink: 0 }}>
                <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost, mb: 0.5 }}>Description</Typography>
                <Typography sx={{ fontSize: '0.88rem', color: c.text.secondary, lineHeight: 1.6 }}>
                  {builderPreview.description}
                </Typography>
              </Box>
            )}

            <ContentPreview content={builderPreview.content} />
          </Box>
        ) : selectedCandidate ? (
          <Box sx={{ height: '100%', minHeight: 0, overflowY: 'auto', overflowX: 'hidden' }}>
            <Box sx={{ p: 4, pb: 3, maxWidth: 1100, display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5, flexShrink: 0 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
                <Typography sx={{ fontSize: '1.4rem', fontWeight: 700, color: c.text.primary, fontFamily: c.font.sans }}>
                  {selectedCandidate.skill_spec.name || 'Untitled Skill Candidate'}
                </Typography>
                <Chip
                  label={`Candidate · ${selectedCandidate.status}`}
                  size="small"
                  sx={{
                    bgcolor: `${c.accent.primary}15`,
                    color: c.accent.primary,
                    fontWeight: 600,
                    fontSize: '0.68rem',
                    height: 22,
                  }}
                />
              </Box>
            </Box>

            {selectedCandidate.skill_spec.command && (
              <Box sx={{ mb: 1.5, flexShrink: 0 }}>
                <Chip
                  icon={<TerminalIcon sx={{ fontSize: 14 }} />}
                  label={`/${selectedCandidate.skill_spec.command}`}
                  size="small"
                  sx={{
                    bgcolor: 'rgba(174,86,48,0.08)', color: c.accent.primary,
                    fontWeight: 500, fontSize: '0.78rem', height: 26,
                  }}
                />
              </Box>
            )}

            <Box sx={{ mb: 1.5, flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 2 }}>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost }}>
                Saved as <strong style={{ color: c.accent.primary, fontWeight: 600 }}>review candidate</strong>.
                {selectedCandidate.install_approved ? ' Approved for install.' : ' Requires approval before install.'}
              </Typography>
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.45, alignItems: 'flex-end' }}>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Tooltip title={selectedCandidate.install_approved ? 'Install approval is already granted.' : 'Run validation and request install approval.'}>
                    <span>
                      <Button
                        variant="outlined"
                        size="small"
                        disabled={selectedCandidate.install_approved || selectedCandidate.status === 'installed'}
                        onClick={handleApproveCandidateInstall}
                        sx={{
                          borderColor: c.border.strong,
                          color: c.text.secondary,
                          '&:hover': { borderColor: c.accent.primary, color: c.accent.primary, bgcolor: 'rgba(174,86,48,0.04)' },
                          textTransform: 'none',
                          borderRadius: `${c.radius.md}px`,
                          px: 2,
                          py: 0.5,
                          fontSize: '0.8rem',
                          fontWeight: 600,
                        }}
                      >
                        Approve install
                      </Button>
                    </span>
                  </Tooltip>
                  <Tooltip title={getInstallDisabledReason(selectedCandidate)}>
                    <span>
                      <Button
                        variant="contained"
                        size="small"
                        disabled={!selectedCandidate.install_approved || selectedCandidate.status === 'installed' || selectedCandidate.status === 'rejected'}
                        onClick={handleInstallCandidate}
                        sx={{
                          bgcolor: c.accent.primary,
                          '&:hover': { bgcolor: c.accent.pressed },
                          textTransform: 'none',
                          borderRadius: `${c.radius.md}px`,
                          px: 2,
                          py: 0.5,
                          fontSize: '0.8rem',
                          fontWeight: 600,
                          boxShadow: 'none',
                        }}
                      >
                        Install
                      </Button>
                    </span>
                  </Tooltip>
                  <Tooltip title={selectedCandidate.status === 'rejected' ? 'Already rejected.' : selectedCandidate.status === 'installed' ? 'Installed candidates cannot be rejected here.' : 'Reject this candidate from review.'}>
                    <span>
                      <Button
                        variant="outlined"
                        size="small"
                        disabled={selectedCandidate.status === 'installed' || selectedCandidate.status === 'rejected'}
                        onClick={handleRejectCandidate}
                        sx={{
                          borderColor: c.border.strong,
                          color: c.status.warning,
                          '&:hover': { borderColor: c.status.warning, bgcolor: `${c.status.warning}10` },
                          textTransform: 'none',
                          borderRadius: `${c.radius.md}px`,
                          px: 2,
                          py: 0.5,
                          fontSize: '0.8rem',
                          fontWeight: 600,
                        }}
                      >
                        Reject
                      </Button>
                    </span>
                  </Tooltip>
                  <Tooltip title="Delete this candidate record.">
                    <span>
                      <Button
                        variant="outlined"
                        size="small"
                        onClick={handleDeleteCandidate}
                        sx={{
                          borderColor: c.border.strong,
                          color: c.status.error,
                          '&:hover': { borderColor: c.status.error, bgcolor: `${c.status.error}10` },
                          textTransform: 'none',
                          borderRadius: `${c.radius.md}px`,
                          px: 2,
                          py: 0.5,
                          fontSize: '0.8rem',
                          fontWeight: 600,
                        }}
                      >
                        Delete
                      </Button>
                    </span>
                  </Tooltip>
                </Box>
                <Typography sx={{ fontSize: '0.7rem', color: c.text.ghost, lineHeight: 1.35 }}>
                  Install: {getInstallDisabledReason(selectedCandidate)}
                </Typography>
              </Box>
            </Box>

            {selectedCandidate.skill_spec.description && (
              <Box sx={{ mb: 2, flexShrink: 0 }}>
                <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost, mb: 0.5 }}>Description</Typography>
                <Typography sx={{ fontSize: '0.88rem', color: c.text.secondary, lineHeight: 1.6 }}>
                  {selectedCandidate.skill_spec.description}
                </Typography>
              </Box>
            )}

            <Box
              sx={{
                mb: 2,
                p: 2,
                borderRadius: `${c.radius.md}px`,
                border: `1px solid ${c.border.subtle}`,
                bgcolor: c.bg.secondary,
                boxShadow: c.shadow.sm,
                flexShrink: 0,
              }}
            >
              <Typography sx={{ fontSize: '0.82rem', color: c.text.primary, fontWeight: 700, mb: 0.75 }}>
                Review summary
              </Typography>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.secondary, lineHeight: 1.5 }}>
                Validation passed. Installation is still blocked until evidence and policy references are attached and install approval is granted.
              </Typography>
              <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.65, mt: 1 }}>
                <MetaChip label="Validation passed" tone="success" />
                <MetaChip label={selectedCandidate.install_approved ? 'Install approved' : 'Install needs approval'} tone={selectedCandidate.install_approved ? 'success' : 'warning'} />
                <MetaChip label={(selectedCandidate.evidence_refs || []).length > 0 ? 'Evidence attached' : 'Evidence missing'} tone={(selectedCandidate.evidence_refs || []).length > 0 ? 'success' : 'warning'} />
                <MetaChip label={(selectedCandidate.policy_refs || []).length > 0 ? 'Policy refs attached' : 'Policy refs missing'} tone={(selectedCandidate.policy_refs || []).length > 0 ? 'success' : 'warning'} />
              </Box>
            </Box>

            <SkillQualityReviewPanel
              review={selectedQualityReview}
              loading={selectedQualityReviewLoading}
              error={selectedQualityReviewError}
            />


            <CollapsibleCandidatePanel
              id="research"
              title="Research contract"
              summary="Read-only check for current-information dependency before finalizing this candidate."
              defaultTone={selectedResearchContractError ? 'error' : selectedResearchContract?.requires_web_research ? 'warning' : 'success'}
            >
              <SkillResearchContractPanel
                contract={selectedResearchContract}
                loading={selectedResearchContractLoading}
                error={selectedResearchContractError}
                approvalLoading={selectedResearchApprovalLoading}
                approvalError={selectedResearchApprovalError}
                executionLoading={selectedResearchExecutionLoading}
                executionError={selectedResearchExecutionError}
                onSetResearchPermission={handleApproveCandidateResearch}
                onExecuteResearch={handleExecuteCandidateResearch}
              />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="harness"
              title="Skill Harness"
              summary="Read-only test cases, dry run simulation, validation, evidence quality, regression and promotion gate."
              defaultTone={selectedHarnessError ? 'error' : selectedHarnessReport?.promotion_gate?.decision === 'promote_ready' ? 'success' : 'warning'}
            >
              <SkillHarnessPanel
                report={selectedHarnessReport}
                loading={selectedHarnessLoading}
                error={selectedHarnessError}
              />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="improvement"
              title="Improvement proposal"
              summary="Review-based proposal and diff preview. Applying updates only this candidate."
              defaultTone={selectedImprovementProposalError ? 'error' : selectedImprovementProposal?.can_generate_diff ? 'warning' : 'default'}
            >
              <SkillImprovementProposalPanel
                proposal={selectedImprovementProposal}
                loading={selectedImprovementProposalLoading}
                error={selectedImprovementProposalError}
                applyLoading={selectedImprovementApplyLoading}
                applyError={selectedImprovementApplyError}
                onApply={handleApplyCandidateImprovement}
              />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="validation"
              title="Validation, gate and evidence details"
              summary="Technical validation details, evidence refs and policy refs."
              defaultTone={(selectedCandidate.validation_errors || []).length > 0 || (selectedCandidate.warnings || []).length > 0 ? 'warning' : 'success'}
            >
              <CandidateReview candidate={selectedCandidate} />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="requirements"
              title="Declared requirements and metadata"
              summary="Tools, MCP servers, providers, models, tags, categories and risks declared by this skill."
            >
              <CandidateRequirements candidate={selectedCandidate} />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="contract"
              title="Requirements contract"
              summary="Read-only diagnostic map. Requirements do not grant permissions or activate tools."
              defaultTone={selectedRequirementsContractError ? 'error' : 'default'}
            >
              <RequirementsContractPanel
                contract={selectedRequirementsContract}
                loading={selectedRequirementsContractLoading}
                error={selectedRequirementsContractError}
              />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="source"
              title="Source and provenance"
              summary="Origin, source format, metadata confidence and provenance details."
            >
              <CandidateSourcePanel candidate={selectedCandidate} />
            </CollapsibleCandidatePanel>

            <CollapsibleCandidatePanel
              id="content"
              title="SKILL.md content"
              summary="Full candidate skill content."
            >
              <ContentPreview content={selectedCandidate.skill_spec.content} />
            </CollapsibleCandidatePanel>
            </Box>
          </Box>
        ) : !selection ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: c.text.ghost, gap: 2 }}>
            <DescriptionIcon sx={{ fontSize: 48, opacity: 0.3 }} />
            <Typography sx={{ fontSize: '0.9rem' }}>Select a skill to view its details</Typography>
          </Box>
        ) : selection.type === 'registry' ? (
          regDetailLoading && !selectedReg ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', pt: 12 }}>
              <CircularProgress size={24} sx={{ color: c.accent.primary }} />
            </Box>
          ) : selectedReg ? (
            <Box sx={{ p: 4, pb: 3, maxWidth: 1100, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
              {/* Header row: name + actions */}
              <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5, flexShrink: 0 }}>
                <Typography sx={{ fontSize: '1.4rem', fontWeight: 700, color: c.text.primary, fontFamily: c.font.sans }}>
                  {selectedReg.name}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, alignItems: 'center' }}>
                  <Button
                    variant="contained"
                    size="small"
                    startIcon={<DownloadIcon sx={{ fontSize: 15 }} />}
                    onClick={handleInstall}
                    sx={{
                      bgcolor: c.accent.primary, '&:hover': { bgcolor: c.accent.pressed },
                      textTransform: 'none', borderRadius: `${c.radius.md}px`, px: 2, py: 0.5,
                      fontSize: '0.8rem', fontWeight: 600, boxShadow: 'none',
                    }}
                  >
                    Save Candidate
                  </Button>
                  <Button
                    variant="outlined"
                    size="small"
                    startIcon={<EditIcon sx={{ fontSize: 15 }} />}
                    onClick={handleEditInstall}
                    sx={{
                      borderColor: c.border.strong, color: c.text.secondary,
                      '&:hover': { borderColor: c.accent.primary, color: c.accent.primary, bgcolor: 'rgba(174,86,48,0.04)' },
                      textTransform: 'none', borderRadius: `${c.radius.md}px`, px: 2, py: 0.5,
                      fontSize: '0.8rem', fontWeight: 600,
                    }}
                  >
                    Edit & Install
                  </Button>
                  {selectedReg.repositoryUrl && (
                    <Tooltip title="View on GitHub">
                      <IconButton
                        size="small"
                        component="a"
                        href={selectedReg.repositoryUrl}
                        sx={{ color: c.text.tertiary, '&:hover': { color: c.text.primary } }}
                      >
                        <OpenInNewIcon sx={{ fontSize: 18 }} />
                      </IconButton>
                    </Tooltip>
                  )}
                </Box>
              </Box>

              <Box sx={{ mb: 1, flexShrink: 0 }}>
                <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost }}>Added by <strong style={{ color: c.text.secondary, fontWeight: 600 }}>Anthropic</strong></Typography>
              </Box>

              <Box sx={{ mb: 2, flexShrink: 0 }}>
                <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost, mb: 0.5 }}>Description</Typography>
                <Typography sx={{ fontSize: '0.88rem', color: c.text.secondary, lineHeight: 1.6 }}>
                  {selectedReg.description}
                </Typography>
              </Box>

              <ContentPreview content={selectedReg.content} />
            </Box>
          ) : null
        ) : selectedLocal ? (
          <Box sx={{ p: 4, pb: 3, maxWidth: 1100, display: 'flex', flexDirection: 'column', height: '100%', minHeight: 0 }}>
            {/* Header row: name + actions */}
            <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 0.5, flexShrink: 0 }}>
              <Typography sx={{ fontSize: '1.4rem', fontWeight: 700, color: c.text.primary, fontFamily: c.font.sans }}>
                {selectedLocal.name}
              </Typography>
              <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center' }}>
                <Tooltip title="Edit">
                  <IconButton size="small" onClick={() => openEdit(selectedLocal)} sx={{ color: c.text.tertiary, '&:hover': { color: c.accent.primary } }}>
                    <EditIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Tooltip>
                <Tooltip title="Delete">
                  <IconButton size="small" onClick={() => handleDelete(selectedLocal.id)} sx={{ color: c.text.tertiary, '&:hover': { color: c.status.error } }}>
                    <DeleteIcon sx={{ fontSize: 18 }} />
                  </IconButton>
                </Tooltip>
              </Box>
            </Box>

            {selectedLocal.command && (
              <Box sx={{ mb: 1.5, flexShrink: 0 }}>
                <Chip
                  icon={<TerminalIcon sx={{ fontSize: 14 }} />}
                  label={`/${selectedLocal.command}`}
                  size="small"
                  sx={{
                    bgcolor: 'rgba(174,86,48,0.08)', color: c.accent.primary,
                    fontWeight: 500, fontSize: '0.78rem', height: 26,
                  }}
                />
              </Box>
            )}

            <Box sx={{ mb: 1, flexShrink: 0 }}>
              <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost }}>Added by <strong style={{ color: c.text.secondary, fontWeight: 600 }}>You</strong></Typography>
            </Box>

            {selectedLocal.description && (
              <Box sx={{ mb: 2, flexShrink: 0 }}>
                <Typography sx={{ fontSize: '0.78rem', color: c.text.ghost, mb: 0.5 }}>Description</Typography>
                <Typography sx={{ fontSize: '0.88rem', color: c.text.secondary, lineHeight: 1.6 }}>
                  {selectedLocal.description}
                </Typography>
              </Box>
            )}

            <ContentPreview content={selectedLocal.content} />
          </Box>
        ) : null}
      </Box>

      {/* ─── Create/Edit Dialog ─── */}
      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        maxWidth="md"
        fullWidth
        PaperProps={{
          sx: { bgcolor: c.bg.surface, backgroundImage: 'none', borderRadius: `${c.radius.lg}px`, border: `${c.border.width} solid ${c.border.subtle}`, boxShadow: c.shadow.lg },
        }}
      >
        <DialogTitle sx={{ color: c.text.primary, fontWeight: 600, fontFamily: c.font.sans }}>
          {editingId ? 'Edit Skill' : formSource === 'registry' ? 'Edit Registry Candidate' : 'New Skill'}
        </DialogTitle>
        <DialogContent sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: '8px !important' }}>
          <TextField
            label="Name"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            fullWidth
            size="small"
            sx={{ '& .MuiOutlinedInput-root': { bgcolor: c.bg.secondary } }}
          />
          <TextField
            label="Description"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            fullWidth
            size="small"
            sx={{ '& .MuiOutlinedInput-root': { bgcolor: c.bg.secondary } }}
          />
          <TextField
            label="Command (slash command name)"
            value={form.command}
            onChange={(e) => setForm({ ...form, command: e.target.value })}
            fullWidth
            size="small"
            placeholder="e.g. my-skill"
            sx={{ '& .MuiOutlinedInput-root': { bgcolor: c.bg.secondary } }}
          />
          <TextField
            label="Content (Markdown)"
            value={form.content}
            onChange={(e) => setForm({ ...form, content: e.target.value })}
            fullWidth
            multiline
            minRows={12}
            maxRows={24}
            sx={{
              '& .MuiOutlinedInput-root': {
                bgcolor: c.bg.secondary, fontFamily: c.font.mono, fontSize: '0.85rem',
              },
            }}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={() => setDialogOpen(false)} sx={{ color: c.text.tertiary, textTransform: 'none' }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={!form.name || !form.content}
            sx={{
              bgcolor: c.accent.primary, '&:hover': { bgcolor: c.accent.pressed },
              textTransform: 'none', borderRadius: `${c.radius.md}px`,
            }}
          >
            {editingId ? 'Save Changes' : formSource === 'registry' ? 'Save Candidate' : 'Create Skill'}
          </Button>
        </DialogActions>
      </Dialog>

      {/* ─── Skill Builder Chat ─── */}
      <SkillBuilderChat
        onSkillPreview={handleBuilderPreview}
        onSkillSaved={handleBuilderSaved}
        expanded={builderOpen}
        onExpandedChange={setBuilderOpen}
      />

      {/* ─── Snackbar ─── */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={3000}
        onClose={() => setSnackbar({ open: false, message: '' })}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar({ open: false, message: '' })}
          severity="success"
          sx={{ bgcolor: c.status.successBg, color: c.status.success, border: `1px solid rgba(38,91,25,0.25)` }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default Skills;
