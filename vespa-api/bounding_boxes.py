import math
from functools import cmp_to_key


def flatten_bounding_boxes(bounding_boxes, max_width=math.inf, max_height=math.inf):
    """
    Flatten dict from terms to bounding boxes into a list sorted by box positions (ltr)

    :param bounding_boxes: dict with shape term => [boxes]
    :param max_width: Width that should not be exceeded
    :param max_height: Height that should not be exceeded
    """
    flat_boxes = []
    for word, boxes in bounding_boxes.items():
        for box in boxes:
            if round(box[1]) <= max_width and round(box[3]) <= max_height:
                flat_boxes.append({
                    'box': box,
                    'word': word
                })
    return sorted(flat_boxes, key=cmp_to_key(__cmp_boxes))


def flatten_snippet_bounding_boxes(bounding_boxes, surrounding_box):
    """
        Flatten dict from terms to bounding boxes into a list sorted by box positions (ltr).
        Also filter out boxes not contained in surrounding box

        :param bounding_boxes: dict with shape term => [boxes]
        :param surrounding_box: outer bounds of snippet
    """
    flat_boxes = flatten_bounding_boxes(bounding_boxes)
    filtered_flat_boxes = __filter_outside_boxes(flat_boxes, surrounding_box)
    return filtered_flat_boxes


def __filter_outside_boxes(bounding_boxes, surrounding_box):
    filtered_boxes = []
    for box_item in bounding_boxes:
        box = box_item['box']
        if round(box[0]) >= surrounding_box[0] and\
                round(box[1]) <= surrounding_box[1] and\
                round(box[2]) >= surrounding_box[2] and\
                round(box[3]) <= surrounding_box[3]:
            adjusted_box = [box[0], box[1], box[2] - surrounding_box[2], box[3] - surrounding_box[2]]
            filtered_boxes.append({'box': adjusted_box, 'word': box_item['word']})
    return filtered_boxes


def __cmp_boxes(x, y):
    box1 = x['box']
    box2 = y['box']
    margin = 10
    height_difference = box1[2] - box2[2]
    abs_height_difference = abs(height_difference)

    if height_difference > margin:
        # first box higher up
        return -1
    elif margin >= abs_height_difference:
        # approx. same height
        if box1[0] < box2[0]:
            return -1
        if box1[0] > box2[0]:
            return 1

        # same starting position
        return 0
    else:
        # second box higher up
        return 1
